# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.integrations.utils import make_post_request
from frappe.utils.data import add_days, now_datetime, time_diff_in_seconds
from frappe.utils.password import get_decrypted_password
from requests.exceptions import HTTPError

from erpnext_shipping.erpnext_shipping.utils import throw_integration_error

SETTINGS_DOCTYPE = "Shiprocket"
LOGIN_URL = "https://apiv2.shiprocket.in/v1/external/auth/login"

# Shiprocket tokens live for 10 days. Renew a day early so a token is
# never sent in its last hours.
TOKEN_VALIDITY_DAYS = 9
MIN_SECONDS_LEFT = 150.0


def get_auth_token(force_refresh=False):
	"""
	Return a Shiprocket API token, logging in again when needed.

	The stored token is reused while it is present and not about to
	expire. Pass force_refresh when Shiprocket rejected the stored token.

	Parameters:
		force_refresh (bool, optional): Ignore the stored token and log in.

	Returns:
		str: The bearer token to send to Shiprocket.
	"""
	if not force_refresh:
		stored_token = __get_stored_token()
		if stored_token:
			return stored_token

	return __login_and_store_token()


def reset_token_on_credential_change(settings):
	"""
	Drop the stored token when the API ID or API password is changed.

	Without this, the token of the old credentials stays in use until
	its stored expiry.

	Parameters:
		settings (Document, required): The Shiprocket settings being saved.

	Returns:
		None
	"""
	# An unchanged password reaches the server as a row of asterisks.
	password = settings.api_password or ""
	password_changed = bool(password) and not settings.is_dummy_password(password)

	if settings.has_value_changed("api_id") or password_changed:
		settings.token = None
		settings.valid_upto = None


def is_unauthorized(exc):
	"""
	Tell if an exception is an HTTP 401 response.

	Parameters:
		exc (Exception, required): The exception raised by a request.

	Returns:
		bool: True when Shiprocket answered 401 Unauthorized.
	"""
	if not isinstance(exc, HTTPError) or exc.response is None:
		return False

	return exc.response.status_code == 401


def __get_stored_token():
	"""
	Read the saved token if it is still safe to use.

	Returns:
		str | None: The saved token, or None when it is missing or
		close to its expiry.
	"""
	token, valid_upto = frappe.db.get_value(
		SETTINGS_DOCTYPE, SETTINGS_DOCTYPE, ["token", "valid_upto"]
	)
	if not token or not valid_upto:
		return None

	if time_diff_in_seconds(valid_upto, now_datetime()) < MIN_SECONDS_LEFT:
		return None

	return token


def __login_and_store_token():
	"""
	Log in to Shiprocket and save the new token with its expiry.

	The token is committed at once so it survives a later rollback of
	the request that triggered the login.

	Returns:
		str: The new bearer token.
	"""
	token = __request_new_token()

	# Not doc.save(): two requests refreshing together must not fail on
	# the document timestamp check.
	frappe.db.set_single_value(SETTINGS_DOCTYPE, {
		"token": token,
		"valid_upto": add_days(now_datetime(), TOKEN_VALIDITY_DAYS),
	})
	frappe.db.commit()

	return token


def __request_new_token():
	"""
	Call the Shiprocket login API with the saved credentials.

	Returns:
		str: The token from the login response. Throws when the login
		fails or the response carries no token.
	"""
	credentials = {
		"email": frappe.db.get_single_value(SETTINGS_DOCTYPE, "api_id"),
		"password": get_decrypted_password(
			SETTINGS_DOCTYPE, SETTINGS_DOCTYPE, "api_password", raise_exception=False
		),
	}

	try:
		response = make_post_request(
			LOGIN_URL,
			headers={"Content-Type": "application/json"},
			data=json.dumps(credentials),
		)
	except Exception as exc:
		throw_integration_error(exc, "logging in to Shiprocket")

	token = response.get("token") if isinstance(response, dict) else None
	if not token:
		frappe.throw(_("Shiprocket login did not return a token. Check the API ID and API Password."))

	return token
