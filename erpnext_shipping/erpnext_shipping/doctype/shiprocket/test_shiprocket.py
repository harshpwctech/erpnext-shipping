# Copyright (c) 2023, Frappe and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from requests.exceptions import HTTPError

from erpnext_shipping.erpnext_shipping.doctype.shiprocket.shiprocket import ShiprocketUtils
from erpnext_shipping.erpnext_shipping.doctype.shiprocket.shiprocket_auth import (
	reset_token_on_credential_change,
)
from erpnext_shipping.erpnext_shipping.utils import throw_integration_error

SHIPROCKET_MODULE = "erpnext_shipping.erpnext_shipping.doctype.shiprocket.shiprocket"


class TestShiprocket(FrappeTestCase):
	"""Token handling and error reporting of the Shiprocket integration."""

	def test_request_logs_in_again_after_401(self):
		"""A rejected token is replaced and the call is repeated once."""
		shiprocket = _make_utils("old-token")
		responses = [_http_error(401), {"ok": True}]

		with patch(f"{SHIPROCKET_MODULE}.make_request", side_effect=responses) as make_request, \
			patch(f"{SHIPROCKET_MODULE}.get_auth_token", return_value="new-token") as get_auth_token:
			result = shiprocket.request("POST", "orders/create/adhoc", {"order_id": "SHIP-1"})

		self.assertEqual(result, {"ok": True})
		get_auth_token.assert_called_once_with(force_refresh=True)
		self.assertEqual(make_request.call_count, 2)

		retry_headers = make_request.call_args_list[1].kwargs["headers"]
		self.assertEqual(retry_headers["Authorization"], "Bearer new-token")

	def test_request_does_not_retry_other_errors(self):
		"""Errors other than 401 are raised without a new login."""
		shiprocket = _make_utils("old-token")

		with patch(f"{SHIPROCKET_MODULE}.make_request", side_effect=_http_error(500)) as make_request, \
			patch(f"{SHIPROCKET_MODULE}.get_auth_token") as get_auth_token:
			self.assertRaises(HTTPError, shiprocket.request, "GET", "settings/company/pickup")

		self.assertEqual(make_request.call_count, 1)
		get_auth_token.assert_not_called()

	def test_token_is_reset_when_api_id_changes(self):
		"""A new API ID drops the token of the old account."""
		settings = _make_settings(api_id_changed=True, api_password="*****")

		reset_token_on_credential_change(settings)

		self.assertIsNone(settings.token)
		self.assertIsNone(settings.valid_upto)

	def test_token_is_reset_when_password_changes(self):
		"""A newly typed password drops the stored token."""
		settings = _make_settings(api_id_changed=False, api_password="new-secret")

		reset_token_on_credential_change(settings)

		self.assertIsNone(settings.token)

	def test_token_is_kept_when_credentials_are_unchanged(self):
		"""Saving the settings without a credential change keeps the token."""
		settings = _make_settings(api_id_changed=False, api_password="*****")

		reset_token_on_credential_change(settings)

		self.assertEqual(settings.token, "stored-token")

	def test_integration_error_shows_provider_message(self):
		"""The provider's message reaches the user and its body is logged."""
		error = _http_error(401, '{"message": "Token has expired", "status_code": 401}')

		with patch("frappe.log_error") as log_error:
			self.assertRaisesRegex(
				frappe.ValidationError,
				"Token has expired",
				throw_integration_error,
				error,
				"creating Shiprocket Shipment",
			)

		self.assertIn("Token has expired", log_error.call_args.kwargs["message"])


def _make_utils(token):
	"""
	Build a ShiprocketUtils without reading the settings or logging in.

	Parameters:
		token (str, required): The token the instance starts with.

	Returns:
		ShiprocketUtils: An instance ready for request() calls.
	"""
	shiprocket = ShiprocketUtils.__new__(ShiprocketUtils)
	shiprocket.base_url = "https://apiv2.shiprocket.in/v1/external/"
	shiprocket.token = token
	return shiprocket


def _make_settings(api_id_changed, api_password):
	"""
	Build a stand-in for the Shiprocket settings document.

	Parameters:
		api_id_changed (bool, required): What has_value_changed("api_id") reports.
		api_password (str, required): Password value as sent by the form.

	Returns:
		MagicMock: Settings with a stored token and expiry.
	"""
	settings = MagicMock()
	settings.api_password = api_password
	settings.token = "stored-token"
	settings.valid_upto = "2026-11-20 10:00:00"
	settings.has_value_changed.return_value = api_id_changed
	settings.is_dummy_password.side_effect = lambda password: set(password) == {"*"}
	return settings


def _http_error(status_code, body=""):
	"""
	Build the HTTPError that requests raises for a failed response.

	Parameters:
		status_code (int, required): HTTP status of the fake response.
		body (str, optional): Response text.

	Returns:
		HTTPError: Error carrying a fake response.
	"""
	response = MagicMock()
	response.status_code = status_code
	response.text = body
	return HTTPError(f"{status_code} Error", response=response)
