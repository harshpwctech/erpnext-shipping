# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt
from __future__ import unicode_literals
import frappe
import json
from frappe import _

def get_tracking_url(carrier, tracking_number):
	# Return the formatted Tracking URL.
	tracking_url = ''
	url_reference = frappe.get_value('Parcel Service', carrier, 'url_reference')
	if url_reference:
		tracking_url = frappe.render_template(url_reference, {'tracking_number': tracking_number})
	return tracking_url

def get_address(address_name):
	fields = ['address_title', 'address_line1', 'address_line2', 'city', 'pincode', 'state', 'country', 'name']
	address = frappe.db.get_value('Address', address_name, fields, as_dict=1)
	address.country_code = frappe.db.get_value('Country', address.country, 'code').upper()

	if not address.pincode or address.pincode == '':
		frappe.throw(_("Postal Code is mandatory to continue. </br> \
				Please set Postal Code for Address <a href='#Form/Address/{0}'>{1}</a>"
			).format(address_name, address_name))
	address.pincode = address.pincode.replace(' ', '')
	address.city = address.city.strip()
	return address

def get_contact(contact_name):
	fields = ['first_name', 'last_name', 'email_id', 'phone', 'mobile_no', 'gender']
	contact = frappe.db.get_value('Contact', contact_name, fields, as_dict=1)

	if not contact.first_name:
		frappe.throw(_("Name is mandatory to continue. </br> \
				Please set Last Name for Contact <a href='#Form/Contact/{0}'>{1}</a>"
			).format(contact_name, contact_name))
	if not contact.phone:
		contact.phone = contact.mobile_no
	return contact

def match_parcel_service_type_carrier(shipment_prices, reference):
	from erpnext_shipping.erpnext_shipping.doctype.parcel_service_type.parcel_service_type import match_parcel_service_type_alias

	for idx, prices in enumerate(shipment_prices):
		service_name = match_parcel_service_type_alias(prices.get(reference[0]), prices.get(reference[1]))
		is_preferred = frappe.db.get_value('Parcel Service Type', service_name, 'show_in_preferred_services_list')
		shipment_prices[idx].service_name = service_name
		shipment_prices[idx].is_preferred = is_preferred
	return shipment_prices

def show_error_alert(action):
	log = frappe.log_error(frappe.get_traceback())
	link_to_log = frappe.utils.get_link_to_form("Error Log", log.name, "See what happened.")
	frappe.msgprint(_('An Error occurred while {0}. {1}').format(action, link_to_log), indicator='orange', alert=True)

def throw_integration_error(exc, action):
	"""
	Log an integration API error and raise it to the frontend.

	The provider's response body goes into the Error Log, so the real
	reason for a failure can be read later.

	Parameters:
		exc (Exception, required): The exception raised by the API call.
		action (str, required): What was being done, e.g. "creating Shiprocket Shipment".

	Returns:
		None: Always throws.
	"""
	response_body = get_error_response_body(exc)

	log_message = frappe.get_traceback()
	if response_body:
		log_message += "\nResponse body:\n" + response_body[:5000]
	log = frappe.log_error(title=_("Error while {0}").format(action), message=log_message)

	api_message = get_api_error_message(response_body)
	if api_message:
		frappe.throw(_("An Error occurred while {0}: {1}").format(action, api_message))

	link_to_log = frappe.utils.get_link_to_form("Error Log", log.name, "See what happened.")
	frappe.throw(_("An Error occurred while {0}. {1}").format(action, link_to_log))

def get_error_response_body(exc):
	"""
	Return the response text carried by an HTTP error.

	Parameters:
		exc (Exception, required): The exception raised by the API call.

	Returns:
		str: The response body, or "" when the exception has none.
	"""
	from requests.exceptions import HTTPError

	if isinstance(exc, HTTPError) and exc.response is not None:
		return exc.response.text or ""
	return ""

def get_api_error_message(response_body):
	"""
	Extract the "message" field from a JSON error response.

	Parameters:
		response_body (str, required): Raw response text from the provider.

	Returns:
		str | None: The provider's message, or None when the body is
		not JSON or has no message.
	"""
	try:
		error_data = json.loads(response_body)
	except ValueError:
		return None

	if isinstance(error_data, dict) and error_data.get("message"):
		return str(error_data["message"])
	return None

def get_lat_long(gps_object):
	gps_object =json.loads(gps_object)
	for feature in gps_object["features"]:
		if feature["geometry"]["type"] == "Point":
			return str(feature["geometry"]["coordinates"][1]), str(feature["geometry"]["coordinates"][0])

def update_tracking_info_daily():
	# Daily scheduled event to update Tracking info for not delivered Shipments
	# Also Updates the related Delivery Notes
	from erpnext_shipping.erpnext_shipping.shipping import update_tracking
	shipments = frappe.get_all('Shipment', filters={
		'docstatus': 1,
		'status': 'Booked',
		'shipment_id': ['!=', ''],
		'tracking_status': ['!=', 'Delivered'],
	})
	for shipment in shipments:
		shipment_doc = frappe.get_doc('Shipment', shipment.name)
		tracking_info = update_tracking(shipment_doc.name, shipment_doc.service_provider, shipment_doc.shipment_id,
				shipment_doc.shipment_delivery_note)

		if tracking_info:
			fields = ['awb_number', 'tracking_status', 'tracking_status_info', 'tracking_url', 'pickup_at', 'delivered_at']
			for field in fields:
				shipment_doc.db_set(field, tracking_info.get(field, None))
			frappe.db.commit()
