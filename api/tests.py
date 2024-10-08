"""
Copyright (c) 2024 Perpetuator LLC

This file is part of Capital Copilot by Perpetuator LLC and is released under the MIT License.
See the LICENSE file in the root of this project for the full license text.
"""

import json
from datetime import date
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import requests
from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.http.response import JsonResponse
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from api.middleware import JSONErrorMiddleware
from api.schema import get_earnings_dates, schema
from api.serializers import (  # CustomPasswordResetSerializer,
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
)
from copilot import settings


class APITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("graphql")  # Use the correct URL name configured in urls.py
        self.valid_ticker = "AAPL"
        self.invalid_ticker = ""

        self.user = User.objects.create_user(username="testuser")
        self.user.set_password("securepassword")
        self.user.save()
        self.token = AccessToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + str(self.token))

    @patch("api.schema.get_earnings_dates")
    @patch("os.getenv")
    @patch("openbb.package.equity_price.ROUTER_equity_price.historical")
    def test_successful_data_retrieval(self, mock_historical, mock_getenv, mock_get_earnings_dates):
        mock_getenv.return_value = "fake_api_key"
        mock_get_earnings_dates.return_value = get_mock_earnings_data()
        mock_squeeze_series = MagicMock()

        def mock_at(index):
            if index[1] == "SQZ_ON":
                return 1
            else:
                return 0

        mock_squeeze_series.at.side_effect = mock_at
        mock_historical.return_value, mock_squeeze_result = get_mock_historical_data()
        mock_squeeze_result.__getitem__.side_effect = lambda key: (
            mock_squeeze_series if key in ["SQZ_ON"] else MagicMock()
        )

        # Simulate authenticated request
        mock_user = MagicMock()
        mock_user.is_authenticated = True
        self.client.force_authenticate(user=mock_user, token=self.token)

        query = """
        {
            getChartData(ticker: "AAPL") {
                success
                message
            }
        }
        """
        response = self.client.post(self.url, data={"query": query}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(json.loads(response.content)["data"]["getChartData"]["success"])


class TestAutocomplete(TestCase):

    def setUp(self):
        self.client = Client(schema)
        self.factory = RequestFactory()

    @patch("openbb.package.equity.ROUTER_equity.search")
    def test_successful_autocomplete_retrieval(self, mock_search):
        mock_user = Mock()
        mock_user.is_authenticated = True

        mock_results = Mock()
        mock_results.results = [
            {"symbol": "AAPL", "name": "Apple Inc.", "cik": "320193"},
            {"symbol": "CART", "name": "Maplebear Inc.", "cik": "1579091"},
            {"symbol": "APLS", "name": "Apellis Pharmaceuticals, Inc.", "cik": "1492422"},
            {"symbol": "APLE", "name": "Apple Hospitality REIT, Inc.", "cik": "1418121"},
            {"symbol": "OLPX", "name": "OLAPLEX HOLDINGS, INC.", "cik": "1868726"},
            {"symbol": "APLD", "name": "Applied Digital Corp.", "cik": "1144879"},
            {"symbol": "CAPL", "name": "CrossAmerica Partners LP", "cik": "1538849"},
            {"symbol": "APLT", "name": "Applied Therapeutics, Inc.", "cik": "1697532"},
            {"symbol": "APLM", "name": "Apollomics Inc.", "cik": "1944885"},
            {"symbol": "PAPL", "name": "Pineapple Financial Inc.", "cik": "1938109"},
            {"symbol": "APLMW", "name": "Apollomics Inc.", "cik": "1944885"},
        ]

        # Mocking the return value of the autocomplete function
        mock_search.return_value = mock_results

        query = """
        {
            getAutocomplete(query: "APL") {
                success
                message
                results {
                    symbol
                    name
                    cik
                }
            }
        }
        """
        request = self.factory.get("/")
        request.user = mock_user
        executed = schema.execute(query, context_value=request)
        self.maxDiff = None
        self.assertDictEqual(
            executed.data,
            {
                "getAutocomplete": {
                    "success": True,
                    "message": None,
                    "results": [
                        {"symbol": "AAPL", "name": "Apple Inc.", "cik": "320193"},
                        {"symbol": "CART", "name": "Maplebear Inc.", "cik": "1579091"},
                        {"symbol": "APLS", "name": "Apellis Pharmaceuticals, Inc.", "cik": "1492422"},
                        {"symbol": "APLE", "name": "Apple Hospitality REIT, Inc.", "cik": "1418121"},
                        {"symbol": "OLPX", "name": "OLAPLEX HOLDINGS, INC.", "cik": "1868726"},
                        {"symbol": "APLD", "name": "Applied Digital Corp.", "cik": "1144879"},
                        {"symbol": "CAPL", "name": "CrossAmerica Partners LP", "cik": "1538849"},
                        {"symbol": "APLT", "name": "Applied Therapeutics, Inc.", "cik": "1697532"},
                        {"symbol": "APLM", "name": "Apollomics Inc.", "cik": "1944885"},
                        {"symbol": "PAPL", "name": "Pineapple Financial Inc.", "cik": "1938109"},
                        {"symbol": "APLMW", "name": "Apollomics Inc.", "cik": "1944885"},
                    ],
                }
            },
        )


def get_mock_historical_data():
    mock_df = Mock()
    mock_df.iterrows.return_value = [
        (
            date(2023, 1, 1),
            {
                "open": 100,
                "high": 110,
                "low": 90,
                "close": 105,
                "volume": 1000,
                "SQZ_ON": 1,
                "SQZ_20_2.0_20_1.5": 12,
                "KCLe_20_1.0": 85,
                "KCBe_20_1.0": 102,
                "KCUe_20_1.0": 120,
                "KCLe_20_2.0": 80,
                "KCBe_20_2.0": 102,
                "KCUe_20_2.0": 125,
                "KCLe_20_3.0": 75,
                "KCBe_20_3.0": 102,
                "KCUe_20_3.0": 130,
            },
        ),
        (
            date(2023, 1, 2),
            {
                "open": 106,
                "high": 115,
                "low": 95,
                "close": 110,
                "volume": 1500,
                "SQZ_ON": 0,
                "SQZ_20_2.0_20_1.5": 13,
                "KCLe_20_1.0": 85,
                "KCBe_20_1.0": 102,
                "KCUe_20_1.0": 120,
                "KCLe_20_2.0": 80,
                "KCBe_20_2.0": 102,
                "KCUe_20_2.0": 125,
                "KCLe_20_3.0": 75,
                "KCBe_20_3.0": 102,
                "KCUe_20_3.0": 130,
            },
        ),
    ]
    mock_ta = Mock()
    mock_df.ta = mock_ta
    mock_squeeze_result = MagicMock()
    mock_ta.squeeze.return_value = mock_squeeze_result
    mock_historical_data = MagicMock()
    mock_historical_data.to_df.return_value = mock_df
    return mock_historical_data, mock_squeeze_result


def get_mock_earnings_data():
    mock_df = pd.DataFrame(
        {
            "symbol": ["AAPL", "AAPL", "AAPL"],
            "name": ["Apple Inc", "Apple Inc", "Apple Inc"],
            "reportDate": ["2024-10-31", "2025-01-30", "2025-04-30"],
            "fiscalDateEnding": ["2024-09-30", "2024-12-31", "2025-03-31"],
            "estimate": ["1.59", "", ""],
            "currency": ["USD", "USD", "USD"],
        }
    )
    return mock_df


class GetEarningsDatesTests(TestCase):
    @patch("requests.Session.get")
    def test_get_earnings_dates_success(self, mock_get):
        # Mock the CSV data returned by the API
        mock_csv = """symbol,name,reportDate,fiscalDateEnding,estimate,currency
AAPL,Apple Inc,2024-10-31,2024-09-30,1.59,USD
AAPL,Apple Inc,2025-01-30,2024-12-31,,USD
AAPL,Apple Inc,2025-04-30,2025-03-31,,USD"""

        # Mock the response from the requests.Session().get call
        mock_response = MagicMock()
        mock_response.content.decode.return_value = mock_csv
        mock_get.return_value = mock_response

        # Expected DataFrame
        expected_df = pd.DataFrame(
            {
                "symbol": ["AAPL", "AAPL", "AAPL"],
                "name": ["Apple Inc", "Apple Inc", "Apple Inc"],
                "reportDate": ["2024-10-31", "2025-01-30", "2025-04-30"],
                "fiscalDateEnding": ["2024-09-30", "2024-12-31", "2025-03-31"],
                "estimate": ["1.59", "", ""],
                "currency": ["USD", "USD", "USD"],
            }
        )

        # Call the function
        api_key = "fake_api_key"
        symbol = "AAPL"
        result_df = get_earnings_dates(symbol, api_key)

        # Assert that the returned DataFrame matches the expected DataFrame
        pd.testing.assert_frame_equal(result_df, expected_df)

    @patch("requests.Session.get")
    def test_get_earnings_dates_failure(self, mock_get):
        # Simulate an exception during the request
        mock_get.side_effect = requests.exceptions.RequestException("API request failed")

        # Call the function
        api_key = "fake_api_key"
        symbol = "AAPL"
        result_df = get_earnings_dates(symbol, api_key)

        # Assert that the function returns None on failure
        self.assertIsNone(result_df)


class ChartDataTests(TestCase):
    def setUp(self):
        self.client = Client(schema)
        self.factory = RequestFactory()

    def test_authentication(self):
        query = """
        {
            getChartData(ticker: "AAPL") {
                success
                message
            }
        }
        """
        request = self.factory.get("/")
        request.user = None
        executed = schema.execute(query, context_value=request)
        self.assertDictEqual(
            executed.formatted,
            {
                "data": {"getChartData": None},
                "errors": [
                    {
                        "message": "Authentication credentials were not provided or are invalid",
                        "locations": [{"line": 3, "column": 13}],
                        "path": ["getChartData"],
                    }
                ],
            },
        )

    def test_invalid_ticker(self):
        mock_user = Mock()
        mock_user.is_authenticated = True
        query = """
        {
            getChartData(ticker: "") {
                success
                message
            }
        }
        """
        request = self.factory.get("/")
        request.user = mock_user
        executed = schema.execute(query, context_value=request)
        self.assertDictEqual(
            executed.formatted, {"data": {"getChartData": {"success": False, "message": "No ticker provided"}}}
        )

    @patch("api.schema.get_earnings_dates")
    @patch("openbb.package.equity_price.ROUTER_equity_price.historical")
    def test_successful_data_retrieval(self, mock_historical, mock_get_earnings_dates):
        mock_df = get_mock_earnings_data()
        mock_get_earnings_dates.return_value = mock_df

        mock_user = Mock()
        mock_user.is_authenticated = True

        mock_historical.return_value, _ = get_mock_historical_data()

        query = """
        {
            getChartData(ticker: "AAPL") {
                success
                message
                squeeze {
                    x
                    y
                }
                ohlc {
                    x
                    y
                }
                volume {
                    x
                    y
                }
                ticker
            }
        }
        """
        request = self.factory.get("/")
        request.user = mock_user
        executed = schema.execute(query, context_value=request)
        self.maxDiff = None
        self.assertDictEqual(
            executed.formatted,
            {
                "data": {
                    "getChartData": {
                        "success": True,
                        "message": None,
                        "squeeze": [
                            {"x": "2023-01-01", "y": [1.0, 12.0]},
                            {"x": "2023-01-02", "y": [0.0, 13.0]},
                        ],
                        "ohlc": [
                            {"x": "2023-01-01", "y": [100.0, 110.0, 90.0, 105.0]},
                            {"x": "2023-01-02", "y": [106.0, 115.0, 95.0, 110.0]},
                        ],
                        "volume": [{"x": "2023-01-01", "y": 1000.0}, {"x": "2023-01-02", "y": 1500.0}],
                        "ticker": "AAPL",
                    }
                }
            },
        )

    @patch("openbb.package.equity_price.ROUTER_equity_price.historical")
    def test_failed_data_retrieval(self, mock_historical):
        mock_user = Mock()
        mock_user.is_authenticated = True

        # Mock OpenBB response to raise an exception
        mock_historical.side_effect = Exception("Data retrieval error")

        query = """
        {
            getChartData(ticker: "AAPL") {
                success
                message
            }
        }
        """
        request = self.factory.get("/")
        request.user = mock_user
        executed = schema.execute(query, context_value=request)
        self.assertEqual(
            executed.formatted,
            {
                "data": {
                    "getChartData": {
                        "success": False,
                        "message": "Failed to load data for 'AAPL': Data retrieval error",
                    }
                }
            },
        )


class RegisterSerializerTests(TestCase):

    def test_valid_data_creates_user(self):
        data = {"username": "testuser", "email": "testuser@example.com", "password": "Testpassword123"}
        serializer = RegisterSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        user = serializer.save()

        self.assertEqual(user.username, data["username"])
        self.assertEqual(user.email, data["email"])
        self.assertTrue(user.check_password(data["password"]))

    def test_missing_username(self):
        data = {"email": "testuser@example.com", "password": "Testpassword123"}
        serializer = RegisterSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_invalid_password(self):
        data = {
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "123",  # Assuming validate_password enforces stronger passwords
        }
        serializer = RegisterSerializer(data=data)
        with self.assertRaises(ValidationError):
            serializer.is_valid(raise_exception=True)


class RegisterViewTests(APITestCase):

    def test_register_user(self):
        url = reverse("rest_register")
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password1": "Newuserpassword123",
            "password2": "Newuserpassword123",
        }
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("e-mail sent", response.data["detail"])
        # self.assertIn("refresh", response.data)

        user = User.objects.get(username=data["username"])
        self.assertEqual(user.email, data["email"])
        self.assertTrue(user.check_password(data["password1"]))

    def test_register_with_invalid_data(self):
        url = reverse("rest_register")
        data = {
            "username": "",
            "email": "newuser@example.com",
            "password1": "Newuserpassword123",
            "password2": "Newuserpassword123",
        }
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)
        # self.assertIn("email", response.data)
        # self.assertIn("password1", response.data)

    def test_register_with_existing_username(self):
        User.objects.create_user(username="existinguser", email="old@example.com", password="Oldpassword123")
        url = reverse("rest_register")
        data = {
            "username": "existinguser",
            "email": "newuser@example.com",
            "password1": "Newuserpassword123",
            "password2": "Newuserpassword123",
        }
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data)

    def test_register_with_existing_email_verified_fails(self):
        user = User.objects.create_user(username="existinguser", email="old@example.com", password="Oldpassword123")
        EmailAddress.objects.create(user_id=user.id, email="old@example.com", verified=True)
        url = reverse("rest_register")
        data = {
            "username": "newuser",
            "email": "old@example.com",
            "password1": "Newuserpassword123",
            "password2": "Newuserpassword123",
        }
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_register_with_existing_email_not_verified_works(self):
        user = User.objects.create_user(username="existinguser", email="old@example.com", password="Oldpassword123")
        EmailAddress.objects.create(user_id=user.id, email="old@example.com", verified=False)
        url = reverse("rest_register")
        data = {
            "username": "newuser",
            "email": "old@example.com",
            "password1": "Newuserpassword123",
            "password2": "Newuserpassword123",
        }
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username=data["username"])
        self.assertEqual(user.email, data["email"])
        self.assertTrue(user.check_password(data["password1"]))


class CustomTokenObtainPairSerializerTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="password123")
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True)

    def test_validate_success(self):
        # Assuming that the serializer uses token creation that would normally require correct credentials
        data = {"username": "testuser", "password": "password123"}
        serializer = CustomTokenObtainPairSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        validated_data = serializer.validate(data)
        self.assertIn("access", validated_data)
        self.assertIn("refresh", validated_data)

    def test_validate_no_user_found(self):
        data = {"username": "nouser", "password": "password123"}
        serializer = CustomTokenObtainPairSerializer(data=data)
        with self.assertRaises(ValidationError) as context:
            serializer.validate(data)
        self.assertIn("email", context.exception.detail)

    def test_validate_email_not_verified(self):
        EmailAddress.objects.filter(user=self.user).update(verified=False)
        data = {"username": "testuser", "password": "password123"}
        serializer = CustomTokenObtainPairSerializer(data=data)
        with self.assertRaises(ValidationError) as context:
            serializer.validate(data)
        self.assertIn("email", context.exception.detail)
        self.assertIn("not verified", context.exception.detail["email"])


class CustomPasswordResetSerializerTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@example.com", password="password123")
        self.factory = RequestFactory()

    # NOTE: Not using custom API code for these anymore, but should the test verify the response of dj-rest-auth?
    # def test_email_validation_success(self):
    #     serializer = CustomPasswordResetSerializer(data={"email": "test@example.com"})
    #     self.assertTrue(serializer.is_valid())
    #
    # def test_email_validation_failure(self):
    #     serializer = CustomPasswordResetSerializer(data={"email": "nonexistent@example.com"})
    #     with self.assertRaises(ValidationError) as context:
    #         serializer.is_valid(raise_exception=True)
    #     self.assertIn("email", context.exception.detail)  # Check that 'email' is a key in the details
    #     self.assertIn(
    #         "No user is associated with this email address.", context.exception.detail["email"][0]
    #     )  # Check the message
    #
    # def test_password_reset(self):
    #     request = self.factory.get("/")  # Simulating a request object
    #     serializer = CustomPasswordResetSerializer(data={"email": "test@example.com"})
    #     serializer.is_valid()
    #     serializer.save(request=request)  # Assuming save triggers the reset flow correctly


class JSONErrorMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = JSONErrorMiddleware(self.get_response)

    def get_response(self, request):
        # This will not raise an exception by itself, allowing us to manually control when exceptions are handled
        return JsonResponse({"success": True}, status=200)

    @patch("logging.exception")
    def test_process_exception_handling(self, mock_logging):
        request = self.factory.get("/")

        # Manually simulate an exception to see how process_exception handles it
        exception = Exception("Test unhandled exception")
        response = self.middleware.process_exception(request, exception)

        # Check that the response is a JSON and 500 status code
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        response_data = json.loads(response.content)
        self.assertIn("exceptions", response_data)

        expected_error = "An error occurred (uncaught)"
        if settings.DEBUG:
            expected_error += " " + str(exception)
        self.assertEqual(response_data["exceptions"], expected_error)

        # Verify logging was called as expected
        mock_logging.assert_called_once_with(expected_error, exc_info=exception)
