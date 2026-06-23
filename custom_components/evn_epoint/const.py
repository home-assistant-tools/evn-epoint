"""Hằng số cho integration EVN ePoint."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "evn_epoint"

# API ePoint (reverse từ app com.icom.epoint v1.18.12)
BASE_URL = "https://api.evnpoint.com/20984/gup2start/rest/"
WORKSPACE = "20984"
APP_VERSION = "1.18.12"
OS_MODEL = "Android 15"
OTP_MD5_PUBLIC_KEY = "CIwX8BZW91ECRKlV15SkLpovkopCptqM"

# Endpoint
EP_LOGIN = "iam/v2/authentication/login"
EP_CHANNEL = "user/api/v2.0/otp/channelAvailable"
EP_SEND_OTP = "user/api/v2.0/otp/sendWithActionWithoutToken"
EP_VERIFY_OTP = "user/api/v2.0/otp/verifyOtpWithActionWithoutToken"
EP_REFRESH = "iam/v1/authentication/refresh-token"
EP_CONTRACTS = "etracker/contracts/withAddress"
EP_CONSUMPTION_INFO = "etracker/v2/consumption/info"
EP_COMPARE_MONTH = "etracker/v2/consumption/compare-month"
EP_BY_MONTH = "etracker/consumption/byMonth"
EP_BY_DATE = "etracker/consumption/byDate"
EP_BILLS = "etracker/bills"

# Config entry keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_DEVICE_KEY = "device_key"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_OTP = "otp"
CONF_CHANNEL = "channel"

ACTION_LOGIN = "LOGIN"
DEFAULT_CHANNEL = "SMS"

# Cập nhật mỗi 2 giờ (dữ liệu EVN chỉ đổi ~1 lần/ngày)
UPDATE_INTERVAL = timedelta(hours=2)
