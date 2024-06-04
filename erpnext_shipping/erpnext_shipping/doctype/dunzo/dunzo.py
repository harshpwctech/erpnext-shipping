# Copyright (c) 2023, Frappe and contributors
# For license information, please see license.txt

import frappe
import json
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.model.document import Document
from pytz import timezone
from datetime import datetime
from frappe.utils.data import add_days, flt, get_datetime, get_system_timezone, now_datetime, time_diff_in_seconds, format_datetime
from frappe.utils.password import get_decrypted_password
from frappe.integrations.utils import make_get_request, make_post_request
from erpnext_shipping.erpnext_shipping.utils import get_lat_long, show_error_alert

DUNZO_PROVIDER = 'Dunzo'
class Dunzo(Document):
	def validate(self):
		if self.enabled:
			self.setup_custom_fields()
	
	def setup_custom_fields(self):
		data_fields = [
			dict(fieldname='pickup_address_gps', label='Pickup Address GPS', fieldtype='Geolocation', insert_after="pickup_address_name", read_only=0, print_hide=1),
			dict(fieldname='delivery_address_gps', label='Delivery Address GPS', fieldtype='Geolocation', insert_after="delivery_address_name", read_only=0, print_hide=1),
			dict(fieldname='collection_amount', label='CoD Collection Amount', fieldtype='Currency', insert_after="shipment_type", read_only=0, print_hide=1)
			]
		for df in data_fields:
			create_custom_field("Shipment", df)

class DunzoUtils():
	def __init__(self):
		self.api_password = get_decrypted_password('Dunzo', 'Dunzo', 'api_password', raise_exception=False)
		self.api_id, self.enabled = frappe.db.get_value('Dunzo', 'Dunzo', ['api_id', 'enabled'])
		if frappe.db.get_value('Dunzo', 'Dunzo', 'sandbox_environment'):
			self.base_url = "https://apis-staging.dunzo.in/"
		else:
			self.base_url = "https://apis-staging.dunzo.in/"

		if not self.enabled:
			link = frappe.utils.get_link_to_form('Dunzo', 'Dunzo', frappe.bold('Dunzo Settings'))
			frappe.throw(_('Please enable Dunzo Integration in {0}'.format(link)), title=_('Mandatory'))
		self.check_auth_token()
	
	def check_auth_token(self):
		dunzo_settings = frappe.get_doc("Dunzo")
		if dunzo_settings.valid_upto:
			if time_diff_in_seconds(dunzo_settings.valid_upto, now_datetime()) < 150.0:
				self.token = self.fetch_auth_token(dunzo_settings)
			else:
				self.token = dunzo_settings.token
		else:
			self.token = self.fetch_auth_token(dunzo_settings)
	
	def fetch_auth_token(self, dunzo_settings):
		url = self.base_url+"api/v1/token"
		headers = {
			"client-secret": self.api_password,
  			"client-id": self.api_id,
			"Content-Type": "application/json"
		}
		token_response = make_get_request(url, headers=headers)
		token = token_response.get("token")
		dunzo_settings.token = token
		dunzo_settings.valid_upto = add_days(now_datetime(), 1)
		dunzo_settings.save(ignore_permissions=True)
		frappe.db.commit()
		return token
	
	def get_available_services(self, pickup_address_gps, delivery_address_gps, cod=False, collection_amount=None):
		if not self.enabled or not self.api_id or not self.api_password:
			frappe.throw(_('Please enable Dunzo Integration'), title=_('Mandatory'))

		url = self.base_url+"api/v2/quote"
		headers = {
			"Content-Type": "application/json",
			"Authorization": self.token,
			"client-id": self.api_id
		}
		pickup_lat, pickup_long = get_lat_long(pickup_address_gps)
		delivery_lat, delivery_long = get_lat_long(delivery_address_gps)
		payload = {
			"pickup_details": [
				{
					"lat": flt(pickup_lat, precision=6),
					"lng": flt(pickup_long, precision=6),
					"reference_id": "pickup-ref"
				}
			],
			"drop_details": [
				{
					"lat": flt(delivery_lat, precision=6),
					"lng": flt(delivery_long, precision=6),
					"reference_id": "drop-ref1"
				}
			],
			"delivery_type": ""
		}
		if cod:
			payload["drop_details"][0]["payment_data"] = {
				"payment_method": "COD",
				"amount": flt(collection_amount)
				}
		try:
			available_services = []
			response_data = make_post_request(
				url=url,
				headers=headers,
				data=json.dumps(payload)
			)
			if response_data:
				frappe.msgprint(response_data)
				available_service = self.get_service_dict(response_data)
				available_services.append(available_service)

				return available_services
			else:
				frappe.throw(_('An Error occurred while fetching Dunzo prices: {0}')
					.format(response_data))
		except Exception:
			show_error_alert("fetching Dunzo prices")

		return []
	
	def create_shipment(self, shipment, pickup_address, delivery_address, delivery_contact=None, pickup_contact=None, cod=False):
		shipment = frappe.get_cached_doc("Shipment", shipment)
		pickup_lat, pickup_long = get_lat_long(shipment.pickup_address_gps)
		delivery_lat, delivery_long = get_lat_long(shipment.delivery_address_gps)
		url = self.base_url+"api/v2/tasks"
		headers = {
			"Content-Type": "application/json",
			"Authorization": self.token,
			"client-id": self.api_id
		}
		payload = {
			"request_id": shipment.name,
			"reference_id": shipment.name,
			"pickup_details": [self.get_pickup_delivery_info(pickup_address, pickup_contact, pickup_lat, pickup_long)],
			"drop_details": [self.get_pickup_delivery_info(delivery_address, delivery_contact, delivery_lat, delivery_long)],
			"payment_method": "DUNZO_CREDIT" if not cod else "COD",
			"delivery_type": ""
		}
		if cod:
			payload["drop_details"][0]["payment_data"] = {
				"payment_method": "COD",
				"amount": flt(shipment.collection_amount)
			}
		try:
			response_data = make_post_request(
				url=url,
				headers=headers,
				data=json.dumps(payload)
			)
			if response_data:
				return {
					'service_provider': DUNZO_PROVIDER,
					'shipment_id': response_data['task_id'],
					'carrier': DUNZO_PROVIDER,
					'carrier_service': DUNZO_PROVIDER,
					"shipment_amount": flt(response_data["estimated_price"], precision=0),
					'awb_number': response_data['task_id'],
				}
			else:
				frappe.throw(_('An Error occurred while creating Shiprocket Shipment: {0}')
					.format(response_data))
		except Exception:
			show_error_alert("creating Shiprocket Shipment")
	
	def get_tracking_data(self, shipment_id):
		url = self.base_url+"api/v1/tasks/{0}/status".format(shipment_id)
		headers = {
			"Content-Type": "application/json",
			"Authorization": self.token,
			"client-id": self.api_id
		}
		try:
			response_data = make_get_request(
				url=url,
				headers=headers
			)
			if response_data:
				tracking_status = "In Progress"
				if response_data["state"] == "delivered":
					tracking_status = "Delivered"
				pickup_at = None
				delivered_at = None
				import time
				for s in response_data["locations_order"]:
					if s["type"] == "pick" and s["state"] == "COMPLETED":
						if frappe.db.get_value('Dunzo', 'Dunzo', 'sandbox_environment'):
							pickup_at = get_datetime()
						else:
							pickup_at = timezone(get_system_timezone()).localize(datetime.utcfromtimestamp(s["event_timestamp"]/1000))
					elif s["type"] == "drop" and s["state"] == "COMPLETED":
						if frappe.db.get_value('Dunzo', 'Dunzo', 'sandbox_environment'):
							delivered_at = get_datetime()
						else:
							delivered_at = timezone(get_system_timezone()).localize(datetime.utcfromtimestamp(s["event_timestamp"]/1000))
				return {
					'awb_number': response_data["task_id"],
					'tracking_status': tracking_status,
					'tracking_status_info': response_data["state"],
					'tracking_url': response_data["tracking_url"] if "tracking_url" in response_data else None,
					'pickup_at': pickup_at,
					'delivered_at': delivered_at
				}
		
		except Exception:
			show_error_alert("track shipment")
	
	def get_service_dict(self, response):
		"""Returns a dictionary with service info."""
		available_service = frappe._dict()
		available_service.service_provider = DUNZO_PROVIDER
		available_service.id = "Dunzo Quote"
		available_service.carrier = DUNZO_PROVIDER
		available_service.carrier_name = DUNZO_PROVIDER
		available_service.service_name = DUNZO_PROVIDER
		available_service.is_preferred = 0
		available_service.real_weight = "Upto 10 KGs"
		available_service.total_price = response["estimated_price"]
		return available_service
	
	def get_pickup_delivery_info(self, address, contact, lat, long):
		return {
			"reference_id": address.name,
			"address": {
				"street_address_1": address.address_line1,
				"street_address_2": address.address_line2,
				"city": address.city,
				"state": address.state,
				"pincode": address.pincode,
				"country": address.country,
				"lng": flt(long, precision=6),
				"lat": flt(lat, precision=6),
				"contact_details": {
					"name": "{0} {1}".format(contact.first_name, contact.last_name) if contact.last_name else contact.first_name,
					"phone_number": contact.phone if contact.phone else "0"
				}
			}
		}