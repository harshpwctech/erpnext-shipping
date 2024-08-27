from frappe.custom.doctype.custom_field.custom_field import create_custom_field
def execute():
    shipment_df = [
        dict(fieldname="delivered_at", label="Delivery Time", fieldtype="Datetime",insert_after="pickup_to", print_hide=1)
        ]
    for sdf in shipment_df:
        create_custom_field("Shipment", sdf)