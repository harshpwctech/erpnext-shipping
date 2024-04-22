# Copyright (c) 2023, Frappe and contributors
# For license information, please see license.txt

import frappe
import json
from frappe import _, log_error
from frappe.integrations.utils import make_get_request, make_post_request
from frappe.model.document import Document
from frappe.utils import data
from frappe.utils.data import add_days, flt, get_datetime, now_datetime, time_diff_in_seconds, format_datetime
from frappe.utils.password import get_decrypted_password
from erpnext_shipping.erpnext_shipping.utils import show_error_alert

SHIPROCKET_PROVIDER = 'Shiprocket'
class Shiprocket(Document):pass

class ShiprocketUtils():
	def __init__(self):
		self.api_password = get_decrypted_password('Shiprocket', 'Shiprocket', 'api_password', raise_exception=False)
		self.api_id, self.enabled = frappe.db.get_value('Shiprocket', 'Shiprocket', ['api_id', 'enabled'])
		self.base_url = "https://apiv2.shiprocket.in/v1/external/"

		if not self.enabled:
			link = frappe.utils.get_link_to_form('Shiprocket', 'Shiprocket', frappe.bold('Shiprocket Settings'))
			frappe.throw(_('Please enable Shiprocket Integration in {0}'.format(link)), title=_('Mandatory'))
		self.check_auth_token()
		
	def check_auth_token(self):
		shiprocket_settings = frappe.get_doc("Shiprocket")
		if shiprocket_settings.valid_upto:
			if time_diff_in_seconds(shiprocket_settings.valid_upto, now_datetime()) < 150.0:
				self.token = self.fetch_auth_token(shiprocket_settings)
			else:
				self.token = shiprocket_settings.token
		else:
			self.token = self.fetch_auth_token(shiprocket_settings)
	
	def fetch_auth_token(self, shiprocket_settings):
		url = self.base_url+"auth/login"
		headers = {
			"Content-Type": "application/json"
		}
		data = {
			"email": self.api_id,
			"password": self.api_password
		}
		token_response = make_post_request(url, headers=headers, data=json.dumps(data))
		token = token_response.get("token")
		shiprocket_settings.token = token
		shiprocket_settings.valid_upto = add_days(now_datetime(), 10)
		shiprocket_settings.save(ignore_permissions=True)
		frappe.db.commit()
		return token

	def get_available_services(self, pickup_pincode, delivery_pincode, weight, cod=False):
		if not self.enabled or not self.api_id or not self.api_password:
			frappe.throw(_('Please enable Shiprocket Integration'), title=_('Mandatory'))

		url = self.base_url+"courier/serviceability/"
		headers = {
			"Content-Type": "application/json",
			"Authorization": "Bearer {0}".format(self.token)
		}
		payload = dict(
			pickup_postcode = pickup_pincode,
			delivery_postcode = delivery_pincode,
			weight = weight,
			cod = cod
		)
		try:
			available_services = []
			response_data = make_get_request(
				url=url,
				headers=headers,
				data=json.dumps(payload)
			)
			if 'data' in response_data and "available_courier_companies" in response_data["data"]:
				if len(response_data["data"]["available_courier_companies"]):
					for response in response_data["data"]["available_courier_companies"]:
						available_service = self.get_service_dict(response)
						available_services.append(available_service)

					return available_services
				else:
					frappe.throw(_('An Error occurred while fetching Shiprocket prices: {0}')
						.format(response_data['message']))
			else:
				frappe.throw(_('An Error occurred while fetching Shiprocket prices: {0}')
					.format(response_data['message']))
		except Exception:
			show_error_alert("fetching Shiprocket prices")

		return []
	
	def create_shipment(self, shipment, pickup_address, delivery_address, shipment_parcel,
		service_info, delivery_notes=None, delivery_contact=None, cod=False):
		if not self.enabled or not self.api_id or not self.api_password:
			return []

		parcel_list = self.get_parcel_list(json.loads(shipment_parcel))
		url = self.base_url+"orders/create/adhoc"
		headers = {
			"Content-Type": "application/json",
			"Authorization": "Bearer {0}".format(self.token)
		}

		payload = self.generate_payload(
			shipment=shipment,
			pickup_address=pickup_address,
			delivery_address=delivery_address,
			delivery_contact=delivery_contact,
			parcel_list=parcel_list,
			delivery_notes=delivery_notes,
			cod=cod,
			service_info=service_info)
		try:
			response_data = make_post_request(
				url=url,
				headers=headers,
				data=json.dumps(payload)
			)
			if 'shipment_id' in response_data:
				awb_number = ''
				awb_url = self.base_url+"courier/assign/awb"
				awb_payload= {
					"shipment_id": response_data["shipment_id"]
				}
				awb_response = make_post_request(awb_url, headers=headers, data=json.dumps(awb_payload))
				if 'awb_assign_status' in awb_response:
					if awb_response["awb_assign_status"] == 1:
						awb_number = awb_response['response']['data']['awb_code']
						pickup_url = self.base_url+"courier/generate/pickup"
						pickup_payload= {
							"shipment_id": [response_data.get("shipment_id")]
						}
						pickup_response = make_post_request(pickup_url, headers=headers, data=json.dumps(pickup_payload))
						if not 'pickup_status' in pickup_response:
							frappe.throw(_('An Error occurred while creating pickup: {0}')
								.format(response_data['message']))
				elif 'message' in response_data:
					frappe.throw(_('An Error occurred while generating AWB: {0}')
						.format(response_data['message']))
				return {
					'service_provider': SHIPROCKET_PROVIDER,
					'shipment_id': response_data['shipment_id'],
					'carrier': awb_response['response']['data']['courier_name'],
					'carrier_service': awb_response['response']['data']['courier_name'],
					"shipment_amount": flt(service_info["total_price"], precision=0) if "total_price" in service_info else 0.00,
					'awb_number': awb_number,
				}
			elif 'message' in response_data:
				frappe.throw(_('An Error occurred while creating Shipment: {0}')
					.format(response_data['message']))
		except Exception:
			show_error_alert("creating Shiprocket Shipment")

	def get_label(self, shipment_id):
		url = self.base_url+"courier/generate/label"
		headers = {
			"Content-Type": "application/json",
			"Authorization": "Bearer {0}".format(self.token)
		}
		payload = {
			"shipment_id": [shipment_id]
		}
		try:
			response_data = make_post_request(
				url=url,
				headers=headers,
				data=json.dumps(payload)
			)
			if 'label_created' in response_data:
				return response_data["label_url"]
			elif 'message' in response_data:
				frappe.throw(_('An Error occurred while generating lable: {0}')
					.format(response_data['message']))
		except Exception:
			show_error_alert("generating Shiprocket lable")
	
	def get_manifest(self, shipment_ids):
		url = self.base_url+"manifests/generate"
		headers = {
			"Content-Type": "application/json",
			"Authorization": "Bearer {0}".format(self.token)
		}
		payload = {
			"shipment_id": shipment_ids
		}
		try:
			response_data = make_post_request(
				url=url,
				headers=headers,
				data=json.dumps(payload)
			)
			if 'manifest_url' in response_data:
				return response_data["manifest_url"]
			elif 'message' in response_data:
				frappe.throw(_('An Error occurred while generating manifest: {0}')
					.format(response_data['message']))
		except Exception:
			show_error_alert("generating Shiprocket manifest")

	def get_tracking_data(self, shipment_id):
		url = self.base_url+"courier/track/shipment/{0}".format(shipment_id)
		headers = {
			"Content-Type": "application/json",
			"Authorization": "Bearer {0}".format(self.token)
		}
		try:
			response_data = make_get_request(
				url=url,
				headers=headers
			)
			if "tracking_data" in response_data:
				tracking_status = "In Progress"
				if response_data["tracking_data"]["shipment_track"][0]["current_status"] == "Delivered":
					tracking_status = "Delivered"
				pickup_at = None
				delivered_at = None
				for s in response_data["tracking_data"]["shipment_track_activities"]:
					status = str(s["sr-status"])
					if status == "42":
						pickup_at = get_datetime(s["date"])
						break
				if tracking_status == "Delivered":
					delivered_at = get_datetime(response_data["tracking_data"]["shipment_track"][0]["delivered_date"])
				return {
					'awb_number': response_data["tracking_data"]["shipment_track"][0]["awb_code"],
					'tracking_status': tracking_status,
					'tracking_status_info': response_data["tracking_data"]["shipment_track"][0]["current_status"],
					'tracking_url': response_data["tracking_data"]["track_url"],
					'pickup_at': pickup_at,
					'delivered_at': delivered_at
				}
		
		except Exception:
			show_error_alert("track shipment")
	
	def get_shipment_details(self, shipment_id):
		shipment_details_url = self.base_url+"shipments/{0}".format(shipment_id)
		headers = {
			"Content-Type": "application/json",
			"Authorization": "Bearer {0}".format(self.token)
		}
		try:
			response_data = make_get_request(
				url=shipment_details_url,
				headers=headers
			)
			order_id = response_data["data"]["order_id"]
			order_details_url = self.base_url+"orders/show/{0}".format(order_id)
			return make_get_request(
				url=order_details_url,
				headers=headers
			)
		except Exception:
			show_error_alert("get shipment details")

	def get_service_dict(self, response):
		"""Returns a dictionary with service info."""
		available_service = frappe._dict()
		available_service.service_provider = SHIPROCKET_PROVIDER
		available_service.id = response['id']
		available_service.carrier = response['courier_name']
		available_service.carrier_name = response['courier_name']
		available_service.service_name = SHIPROCKET_PROVIDER
		available_service.is_preferred = 0
		available_service.real_weight = response['base_weight']
		available_service.total_price = response['rate']
		return available_service
	
	def get_parcel_list(self, shipment_parcel):
		parcel_list = frappe._dict(dict(weight = 0, height = 0, length = 0, width = 0))
		for p in shipment_parcel:
			parcel_list.weight += p["weight"]*p["count"]
			parcel_list.height += p["height"]*p["count"]
			parcel_list.length += p["length"]*p["count"]
			parcel_list.width += p["width"]*p["count"]
		return parcel_list
	
	def generate_payload(self, shipment, pickup_address, delivery_address, delivery_contact,
		parcel_list, delivery_notes, cod, service_info=None):
		order_items = self.get_order_items(delivery_notes)
		payload = {
			"order_id": shipment,
			"order_date": format_datetime(get_datetime()),
			"pickup_location": self.get_pickup_location(pickup_address),
			"billing_customer_name": delivery_contact.first_name,
			"billing_last_name": delivery_contact.last_name if delivery_contact.last_name else "",
			"billing_address": delivery_address.address_line1,
			"billing_address_2": delivery_address.address_line2,
			"billing_city": delivery_address.city,
			"billing_pincode": delivery_address.pincode,
			"billing_state": delivery_address.state,
			"billing_country": delivery_address.country,
			"billing_email": delivery_contact.email,
			"billing_phone": delivery_contact.phone,
			"shipping_is_billing": True,
			"order_items": order_items,
			"payment_method": "Prepaid" if not cod else "COD",
			"sub_total": sum(item["selling_price"]*item["units"] for item in order_items),
			"length": float(parcel_list.length),
			"breadth": float(parcel_list.width),
			"height": float(parcel_list.height),
			"weight": float(parcel_list.weight)
		}
		invoice_number = get_invoice_number(delivery_notes)
		if invoice_number:
			payload["invoice_number"] = invoice_number
		
		return payload
	
	def get_order_items(self, delivery_notes):
		order_items = []
		for dn in list(set(eval(delivery_notes))):
			delivery_note = frappe.get_doc("Delivery Note", dn)
			for item in delivery_note.items:
				tax_rate = get_item_tax_amount_from_delivery_note(item.item_code, delivery_note)
				order_item = {
					"name": item.item_name,
					"sku": item.item_code[:50],
					"units": int(item.qty),
					"selling_price": int(item.rate*(1+tax_rate/100)),
					"tax": tax_rate,
					"hsn": int(item.gst_hsn_code) if item.gst_hsn_code else ""
				}
				order_items.append(order_item)
		
		return order_items
	
	def get_pickup_location(self, pickup_address):
		get_pickup_address_url = self.base_url+"settings/company/pickup"
		headers = {
			"Content-Type": "application/json",
			"Authorization": "Bearer {0}".format(self.token)
		}
		try:
			response_data = make_get_request(
				url=get_pickup_address_url,
				headers=headers
			)
			if not any(pickup_location["pickup_location"] == pickup_address.name[:36] for pickup_location in response_data["data"]["shipping_address"]):
				add_pickup_address_url = self.base_url+"settings/company/addpickup"
				add_pickup_address_payload= {
					"pickup_location": pickup_address.name[:36],
					"name": response_data["data"]["shipping_address"][0]["name"],
					"email": response_data["data"]["shipping_address"][0]["email"],
					"phone": response_data["data"]["shipping_address"][0]["phone"],
					"address": "Address Line 1: {0}".format(pickup_address.address_line1),
					"address_2": pickup_address.address_line2,
					"city": pickup_address.city,
					"state": pickup_address.state,
					"country": pickup_address.country,
					"pin_code": pickup_address.pincode
				}
				add_pickup_address_response = make_post_request(add_pickup_address_url, headers=headers, data=json.dumps(add_pickup_address_payload))
				if 'success' in add_pickup_address_response:
					return pickup_address.name[:36]
				else:
					frappe.throw(_('An Error occurred while adding pickup location: {0}')
						.format(add_pickup_address_response['message']))
			else:
				return pickup_address.name[:36]
		except Exception:
			show_error_alert("getting pickup location")

def get_invoice_number(delivery_notes):
	for dn in list(set(eval(delivery_notes))):
		si = frappe.db.get_value("Sales Invoice Item", filters={"delivery_note": dn, "docstatus": 1}, fieldname="parent", for_update=True)
		if si:
			return si
	return None
			
def get_item_tax_amount_from_delivery_note(item, delivery_note):
	tax_rate = 0.0
	if delivery_note.total_taxes_and_charges:
		for tax in delivery_note.taxes:
			if getattr(tax, "category", None) and tax.category=="Valuation":
				continue

			item_tax_map = json.loads(tax.item_wise_tax_detail) if tax.item_wise_tax_detail else {}
			if item_tax_map:
				for item_code, tax_data in item_tax_map.items():
					if item_code == item:
						if isinstance(tax_data, list):
							tax_rate += flt(tax_data[0])
	return int(tax_rate)


