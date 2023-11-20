frappe.ui.form.on('Shipment Manifest', {
	refresh: function (frm) {
		// Add any initialization code here
	},
	scan_barcode: function (frm) {
		if (!frm.doc.scan_barcode) {
			return false;
		}
		frm.trigger('check_already_scanned');
	},
	check_already_scanned: function (frm) {
		// Check if the AWB number is already scanned
		const manifest_items = frm.doc.manifest_items || [];
		const already_scanned = manifest_items.some(d => d.awb_number === frm.doc.scan_barcode);

		if (already_scanned) {
			frappe.show_alert({
				message: __("Package already added in this manifest"),
				indicator: "red"
			});
			clearBarcodeField(frm);
			return;
		}
		frm.trigger('fetch_shipment');
	},
	fetch_shipment: function (frm) {
		// Fetch the shipment details
		frappe.call({
			method: 'frappe.client.get_list',
			args: {
				doctype: 'Shipment',
				filters: {
					awb_number: frm.doc.scan_barcode,
					service_provider: frm.doc.service_provider
				},
				fields: ['name', 'awb_number', 'shipment_id'],
				limit: 1
			},
			callback: function (response) {
				if (response.message && response.message.length > 0) {
					// AWB number found in 'Shipment' doctype
					// Check if service_provider is Shiprocket and validate the pickup_id
					validatePickupId(frm, response.message[0].shipment_id).then((result) => {
						if (result) {
							// Add the child table entry
							frm.add_child('manifest_items', {
								shipment: response.message[0].name,
								awb_number: response.message[0].awb_number,
								shipment_id: response.message[0].shipment_id
							});

							// Refresh the form to display the newly added child table entry
							frm.refresh_field('manifest_items');
							clearBarcodeField(frm);
						} 
					});
				}
				else {
					// AWB number not found in 'Shipment' doctype, show a message or perform any other action
					frappe.msgprint('AWB number not found in Shipment doctype.');
					clearBarcodeField(frm);
				}
			},
			error: function (err) {
				// Handle any error that may occur during the server call
				console.error('Error occurred:', err);
				clearBarcodeField(frm);
			}
		});
	}
});

function clearBarcodeField(frm) {
	// Clear the scan_barcode field
	frm.set_value('scan_barcode', '');
}

function validatePickupId(frm, shipment_id) {
	return new Promise((resolve, reject) => {
		if (frm.doc.service_provider === "Shiprocket") {
			frappe.call({
				method: 'erpnext_shipping.erpnext_shipping.shipping.get_shipment_details',
				args: {
					shipment_id: shipment_id,
					service_provider: frm.doc.service_provider
				},
				callback: function (response) {
					if (response) {
						const fetchedPickupId = response.message.data.pickup_id;
						if (frm.doc.pickup_id && frm.doc.pickup_id !== fetchedPickupId) {
							frappe.msgprint('Barcode belongs to a different pickup provider. Cannot add to the manifest.');
							clearBarcodeField(frm);
							resolve(false);
						} else {
							// Set the pickup_id in the Shipment Manifest doc itself
							frm.set_value('pickup_id', fetchedPickupId);
							frm.refresh_field('pickup_id');
							resolve(true);
						}
					} else {
						frappe.msgprint('Error: Unable to fetch shipment details from the API response.');
						clearBarcodeField(frm);
						resolve(false);
					}
				},
				error: function (err) {
					// Handle any error that may occur during the server call
					console.error('Error occurred:', err);
					frappe.msgprint('Error: Unable to fetch shipment details from the API.');
					clearBarcodeField(frm);
					reject(false);
				}
			});
		} else {
			// No validation required for other service providers
			resolve(true);
		}
	});
}
