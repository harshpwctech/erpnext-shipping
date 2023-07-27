# Copyright (c) 2023, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from erpnext_shipping.erpnext_shipping.doctype.shiprocket.shiprocket import SHIPROCKET_PROVIDER, ShiprocketUtils
from frappe.utils.file_manager import save_url

class ShipmentManifest(Document):
	def on_submit(self):
		self.create_manifest()
	
	def create_manifest(self):
		shipment_ids = []
		manifest_url = None
		for m in self.manifest_items:
			shipment_ids.append(m.shipment_id)
		if self.service_provider == SHIPROCKET_PROVIDER:
			shiprocket = ShiprocketUtils()
			manifest_url = shiprocket.get_manifest(shipment_ids)
		
		if manifest_url:
			save_url(manifest_url, self.name, self.doctype, self.name, folder="Home", is_private=True)


