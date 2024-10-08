# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt
from __future__ import unicode_literals
import frappe
import json
from six import string_types
from frappe import _
from frappe.utils import flt
from erpnext.stock.doctype.shipment.shipment import get_company_contact
from erpnext_shipping.erpnext_shipping.utils import get_address, get_contact, match_parcel_service_type_carrier
from erpnext_shipping.erpnext_shipping.doctype.letmeship.letmeship import LETMESHIP_PROVIDER, LetMeShipUtils
from erpnext_shipping.erpnext_shipping.doctype.packlink.packlink import PACKLINK_PROVIDER, PackLinkUtils
from erpnext_shipping.erpnext_shipping.doctype.sendcloud.sendcloud import SENDCLOUD_PROVIDER, SendCloudUtils
from erpnext_shipping.erpnext_shipping.doctype.shiprocket.shiprocket import SHIPROCKET_PROVIDER, ShiprocketUtils
from erpnext_shipping.erpnext_shipping.doctype.dunzo.dunzo import DUNZO_PROVIDER, DunzoUtils

@frappe.whitelist()
def fetch_shipping_rates(shipment_doc, pickup_from_type, delivery_to_type, pickup_address_name, delivery_address_name,
	shipment_parcel, description_of_content, pickup_date, value_of_goods,
	pickup_contact_name=None, delivery_contact_name=None, cod=False):
	# Return Shipping Rates for the various Shipping Providers
	shipment_prices = []
	letmeship_enabled = frappe.db.get_single_value('LetMeShip','enabled')
	packlink_enabled = frappe.db.get_single_value('Packlink','enabled')
	sendcloud_enabled = frappe.db.get_single_value('SendCloud','enabled')
	shiprocket_enabled = frappe.db.get_single_value('Shiprocket','enabled')
	dunzo_enabled = frappe.db.get_single_value('Dunzo','enabled')
	pickup_address = get_address(pickup_address_name)
	delivery_address = get_address(delivery_address_name)

	if letmeship_enabled:
		pickup_contact = None
		delivery_contact = None
		if pickup_from_type != 'Company':
			pickup_contact = get_contact(pickup_contact_name)
		else:
			pickup_contact = get_company_contact(user=pickup_contact_name)

		if delivery_to_type != 'Company':
			delivery_contact = get_contact(delivery_contact_name)
		else:
			delivery_contact = get_company_contact(user=pickup_contact_name)

		letmeship = LetMeShipUtils()
		letmeship_prices = letmeship.get_available_services(
			delivery_to_type=delivery_to_type,
			pickup_address=pickup_address,
			delivery_address=delivery_address,
			shipment_parcel=shipment_parcel,
			description_of_content=description_of_content,
			pickup_date=pickup_date,
			value_of_goods=value_of_goods,
			pickup_contact=pickup_contact,
			delivery_contact=delivery_contact,
		) or []
		letmeship_prices = match_parcel_service_type_carrier(letmeship_prices, ['carrier', 'carrier_name'])
		shipment_prices = shipment_prices + letmeship_prices

	if packlink_enabled:
		packlink = PackLinkUtils()
		packlink_prices = packlink.get_available_services(
			pickup_address=pickup_address,
			delivery_address=delivery_address,
			shipment_parcel=shipment_parcel,
			pickup_date=pickup_date
		) or []
		packlink_prices = match_parcel_service_type_carrier(packlink_prices, ['carrier_name', 'carrier'])
		shipment_prices = shipment_prices + packlink_prices

	if sendcloud_enabled and pickup_from_type == 'Company':
		sendcloud = SendCloudUtils()
		sendcloud_prices = sendcloud.get_available_services(
			delivery_address=delivery_address,
			shipment_parcel=shipment_parcel
		) or []
		shipment_prices = shipment_prices + sendcloud_prices[:4] # remove after fixing scroll issue
	if shiprocket_enabled:
		shipment_parcel = json.loads(shipment_parcel)
		weight = 0
		for parcel in shipment_parcel:
			weight += parcel.get('weight')
		shiprocket = ShiprocketUtils()
		shiprocket_prices = shiprocket.get_available_services(
			pickup_pincode=pickup_address.pincode,
			delivery_pincode=delivery_address.pincode,
			weight = weight,
			cod=cod
		)
		shipment_prices = shipment_prices + shiprocket_prices
	if dunzo_enabled:
		shipment = frappe.get_doc("Shipment", shipment_doc)
		dunzo = DunzoUtils()
		dunzo_prices = dunzo.get_available_services(
			pickup_address_gps=shipment.pickup_address_gps,
			delivery_address_gps=shipment.delivery_address_gps,
			cod=cod,
			collection_amount=shipment.collection_amount
		)
		shipment_prices = shipment_prices + dunzo_prices
	shipment_prices = sorted(shipment_prices, key=lambda k:k['total_price'])
	return shipment_prices

@frappe.whitelist()
def create_shipment(shipment, pickup_from_type, delivery_to_type, pickup_address_name,
		delivery_address_name, shipment_parcel, description_of_content, pickup_date,
		value_of_goods, service_data, shipment_notific_email=None, tracking_notific_email=None,
		pickup_contact_name=None, delivery_contact_name=None, delivery_notes=[]):
	# Create Shipment for the selected provider
	service_info = json.loads(service_data)
	shipment_info, pickup_contact,  delivery_contact = None, None, None
	pickup_address = get_address(pickup_address_name)
	delivery_address = get_address(delivery_address_name)

	if pickup_from_type != 'Company':
		pickup_contact = get_contact(pickup_contact_name)
	else:
		pickup_contact = get_company_contact(user=pickup_contact_name)

	if delivery_to_type != 'Company':
		delivery_contact = get_contact(delivery_contact_name)
	else:
		delivery_contact = get_company_contact(user=pickup_contact_name)

	if service_info['service_provider'] == LETMESHIP_PROVIDER:
		letmeship = LetMeShipUtils()
		shipment_info = letmeship.create_shipment(
			pickup_address=pickup_address,
			delivery_address=delivery_address,
			shipment_parcel=shipment_parcel,
			description_of_content=description_of_content,
			pickup_date=pickup_date,
			value_of_goods=value_of_goods,
			pickup_contact=pickup_contact,
			delivery_contact=delivery_contact,
			service_info=service_info
		)

	if service_info['service_provider'] == PACKLINK_PROVIDER:
		packlink = PackLinkUtils()
		shipment_info = packlink.create_shipment(
			pickup_address=pickup_address,
			delivery_address=delivery_address,
			shipment_parcel=shipment_parcel,
			description_of_content=description_of_content,
			pickup_date=pickup_date,
			value_of_goods=value_of_goods,
			pickup_contact=pickup_contact,
			delivery_contact=delivery_contact,
			service_info=service_info,
		)

	if service_info['service_provider'] == SENDCLOUD_PROVIDER:
		sendcloud = SendCloudUtils()
		shipment_info = sendcloud.create_shipment(
			shipment=shipment,
			delivery_address=delivery_address,
			shipment_parcel=shipment_parcel,
			description_of_content=description_of_content,
			value_of_goods=value_of_goods,
			delivery_contact=delivery_contact,
			service_info=service_info,
		)
	
	if service_info['service_provider'] == SHIPROCKET_PROVIDER:
		shiprocket = ShiprocketUtils()
		shipment_info = shiprocket.create_shipment(
			shipment=shipment,
			pickup_address=pickup_address,
			delivery_address=delivery_address,
			shipment_parcel=shipment_parcel,
			service_info=service_info,
			delivery_notes=delivery_notes,
			delivery_contact=delivery_contact	
		)
	
	if service_info['service_provider'] == DUNZO_PROVIDER:
		dunzo = DunzoUtils()
		shipment_info = dunzo.create_shipment(
			shipment=shipment,
			pickup_address=pickup_address,
			delivery_address=delivery_address,
			delivery_contact=delivery_contact,
			pickup_contact=pickup_contact	
		)

	if shipment_info:
		fields = ['service_provider', 'carrier', 'carrier_service', 'shipment_id', 'shipment_amount', 'awb_number']
		for field in fields:
			frappe.db.set_value('Shipment', shipment, field, shipment_info.get(field))
		frappe.db.set_value('Shipment', shipment, 'status', 'Booked')

		if delivery_notes:
			update_delivery_note(delivery_notes=delivery_notes, shipment_info=shipment_info)

	return shipment_info

@frappe.whitelist()
def print_shipping_label(service_provider, shipment_id):
	shipping_label = None
	if service_provider == LETMESHIP_PROVIDER:
		letmeship = LetMeShipUtils()
		shipping_label = letmeship.get_label(shipment_id)
	elif service_provider == PACKLINK_PROVIDER:
		packlink = PackLinkUtils()
		shipping_label = packlink.get_label(shipment_id)
	elif service_provider == SENDCLOUD_PROVIDER:
		sendcloud = SendCloudUtils()
		shipping_label = sendcloud.get_label(shipment_id)
	elif service_provider == SHIPROCKET_PROVIDER:
		shiprocket = ShiprocketUtils()
		shipping_label = shiprocket.get_label(shipment_id)
	return shipping_label

@frappe.whitelist()
def update_tracking(shipment, service_provider, shipment_id, delivery_notes=[]):
	# Update Tracking info in Shipment
	tracking_data = None
	if service_provider == LETMESHIP_PROVIDER:
		letmeship = LetMeShipUtils()
		tracking_data = letmeship.get_tracking_data(shipment_id)
	elif service_provider == PACKLINK_PROVIDER:
		packlink = PackLinkUtils()
		tracking_data = packlink.get_tracking_data(shipment_id)
	elif service_provider == SENDCLOUD_PROVIDER:
		sendcloud = SendCloudUtils()
		tracking_data = sendcloud.get_tracking_data(shipment_id)
	elif service_provider == SHIPROCKET_PROVIDER:
		shiprocket = ShiprocketUtils()
		tracking_data = shiprocket.get_tracking_data(shipment_id)
	elif service_provider == DUNZO_PROVIDER:
		dunzo = DunzoUtils()
		tracking_data = dunzo.get_tracking_data(shipment_id)

	if tracking_data:
		fields = ['awb_number', 'tracking_status', 'tracking_status_info', 'tracking_url', 'delivered_at']
		for field in fields:
			frappe.db.set_value('Shipment', shipment, field, tracking_data.get(field))

		if delivery_notes:
			update_delivery_note(delivery_notes=delivery_notes, tracking_info=tracking_data)
	
	return tracking_data

@frappe.whitelist()
def get_shipment_details(service_provider, shipment_id):
	if service_provider == SHIPROCKET_PROVIDER:
		shiprocket = ShiprocketUtils()
		shipment_details = shiprocket.get_shipment_details(shipment_id)

	return shipment_details

def update_delivery_note(delivery_notes, shipment_info=None, tracking_info=None):
	# Update Shipment Info in Delivery Note
	# Using db_set since some services might not exist
	if isinstance(delivery_notes, string_types):
		delivery_notes = json.loads(delivery_notes)

	delivery_notes = list(set(delivery_notes))

	for delivery_note in delivery_notes:
		dl_doc = frappe.get_doc('Delivery Note', delivery_note)
		if shipment_info:
			dl_doc.db_set('delivery_type', 'Parcel Service')
			dl_doc.db_set('parcel_service', shipment_info.get('carrier'))
			dl_doc.db_set('parcel_service_type', shipment_info.get('carrier_service'))
		if tracking_info:
			dl_doc.db_set('tracking_number', tracking_info.get('awb_number'))
			dl_doc.db_set('tracking_url', tracking_info.get('tracking_url'))
			dl_doc.db_set('tracking_status', tracking_info.get('tracking_status'))
			dl_doc.db_set('tracking_status_info', tracking_info.get('tracking_status_info'))