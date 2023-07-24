(()=>{frappe.templates.shipment_service_selector=`{% if (data.preferred_services.length || data.other_services.length) { %}
	<div style="overflow-x:scroll;">
		<h5>{{ __("Preferred Services") }}</h5>
		{% if (data.preferred_services.length) { %}
			<table class="table table-bordered table-hover">
				<thead class="grid-heading-row">
					<tr>
						{% for (var i = 0; i < header_columns.length; i++) { %}
							<th style="padding-left: 12px;">{{ header_columns[i] }}</th>
						{% } %}
					</tr>
				</thead>
				<tbody>
					{% for (var i = 0; i < data.preferred_services.length; i++) { %}
						<tr id="data-preferred-{{i}}">
							<td class="service-info" style="width:20%;">{{ data.preferred_services[i].service_provider }}</td>
							<td class="service-info" style="width:20%;">{{ data.preferred_services[i].carrier }}</td>
							<td class="service-info" style="width:40%;">{{ data.preferred_services[i].service_name }}</td>
							<td class="service-info" style="width:20%;">{{ format_currency(data.preferred_services[i].total_price, "EUR", 2) }}</td>
							<td style="width:10%;vertical-align: middle;">
								<button
									data-type="preferred_services"
									id="data-preferred-{{i}}" type="button" class="btn">
									Select
								</button>
							</td>
						</tr>
					{% } %}
				</tbody>
			</table>
		{% } else { %}
			<div style="text-align: center; padding: 10px;">
				<span class="text-muted">
					{{ __("No Preferred Services Available") }}
				</span>
			</div>
		{% } %}
		<h5>{{ __("Other Services") }}</h5>
		{% if (data.other_services.length) { %}
			<table class="table table-bordered table-hover">
				<thead class="grid-heading-row">
					<tr>
						{% for (var i = 0; i < header_columns.length; i++) { %}
							<th style="padding-left: 12px;" >{{ header_columns[i] }}</th>
						{% } %}
					</tr>
				</thead>
				<tbody>
					{% for (var i = 0; i < data.other_services.length; i++) { %}
						<tr id="data-other-{{i}}">
							<td class="service-info" style="width:20%;">{{ data.other_services[i].service_provider }}</td>
							<td class="service-info" style="width:20%;">{{ data.other_services[i].carrier }}</td>
							<td class="service-info" style="width:40%;">{{ data.other_services[i].service_name }}</td>
							<td class="service-info" style="width:20%;">{{ format_currency(data.other_services[i].total_price, "INR", 2) }}</td>
							<td style="width:10%;vertical-align: middle;">
								<button
									data-type="other_services"
									id="data-other-{{i}}" type="button" class="btn">
									Select
								</button>
							</td>
						</tr>
					{% } %}
				</tbody>
			</table>
		{% } else { %}
		<div style="text-align: center; padding: 10px;">
			<span class="text-muted">
				{{ __("No Services Available") }}
			</span>
		</div>
		{% } %}
	</div>
{% } else { %}
	<div style="text-align: center; padding: 10px;">
		<span class="text-muted">
			{{ __("No Services Available") }}
		</span>
	</div>
{% } %}

<style type="text/css" media="screen">
.modal-dialog {
	width: 750px;
}
.service-info {
	vertical-align: middle !important;
	padding-left: 12px !important;
}
.btn:hover {
	background-color: #dedede;
}
.ship {
	font-size: 16px;
}
</style>`;})();
<<<<<<< HEAD:erpnext_shipping/public/dist/js/erpnext_shipment_service_selector.bundle.3Q7NQBPN.js
//# sourceMappingURL=erpnext_shipment_service_selector.bundle.3Q7NQBPN.js.map
=======
//# sourceMappingURL=erpnext_shipment_service_selector.bundle.PMSJDQ57.js.map
>>>>>>> 2655e2dd6225e2433bd1b75504990f9456a83ae5:erpnext_shipping/public/dist/js/erpnext_shipment_service_selector.bundle.PMSJDQ57.js
