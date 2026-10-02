import time
import unittest
from urllib.parse import parse_qsl, urlencode

from helpers import ADMIN_ID, BOT_TOKEN, OTHER_ID, init_data, sign
from auth import admin_user, validate_init_data


class ValidateInitDataTest(unittest.TestCase):
    def test_valid_signature_returns_user(self):
        user = validate_init_data(init_data(), BOT_TOKEN)
        self.assertEqual(user["id"], ADMIN_ID)

    def test_wrong_bot_token_rejected(self):
        self.assertIsNone(validate_init_data(init_data(token="999:other"), BOT_TOKEN))

    def test_tampered_user_id_rejected(self):
        fields = dict(parse_qsl(init_data(user_id=OTHER_ID)))
        fields["user"] = fields["user"].replace(str(OTHER_ID), str(ADMIN_ID))
        self.assertIsNone(validate_init_data(urlencode(fields), BOT_TOKEN))

    def test_missing_hash_rejected(self):
        fields = dict(parse_qsl(init_data()))
        del fields["hash"]
        self.assertIsNone(validate_init_data(urlencode(fields), BOT_TOKEN))

    def test_fake_hash_rejected(self):
        fields = dict(parse_qsl(init_data()))
        fields["hash"] = "0" * 64
        self.assertIsNone(validate_init_data(urlencode(fields), BOT_TOKEN))

    def test_expired_rejected(self):
        old = time.time() - 2 * 24 * 3600
        self.assertIsNone(validate_init_data(init_data(auth_date=old), BOT_TOKEN))

    def test_from_future_rejected(self):
        self.assertIsNone(validate_init_data(init_data(auth_date=time.time() + 3600), BOT_TOKEN))

    def test_empty_and_garbage_rejected(self):
        for value in ["", "abc", "hash=", "user=1&hash=zz", None]:
            self.assertIsNone(validate_init_data(value, BOT_TOKEN))

    def test_empty_bot_token_rejects_everything(self):
        self.assertIsNone(validate_init_data(init_data(token=""), ""))

    def test_duplicate_keys_rejected(self):
        self.assertIsNone(validate_init_data(init_data() + "&user=%7B%22id%22%3A111%7D", BOT_TOKEN))

    def test_user_without_numeric_id_rejected(self):
        data = sign({"auth_date": str(int(time.time())), "user": '{"id":"111"}'})
        self.assertIsNone(validate_init_data(data, BOT_TOKEN))


class AdminUserTest(unittest.TestCase):
    def test_admin_allowed(self):
        self.assertIsNotNone(admin_user(init_data(), BOT_TOKEN, {ADMIN_ID}))

    def test_other_user_with_valid_signature_denied(self):
        self.assertIsNone(admin_user(init_data(user_id=OTHER_ID), BOT_TOKEN, {ADMIN_ID}))

    def test_no_admins_configured_denied(self):
        self.assertIsNone(admin_user(init_data(), BOT_TOKEN, set()))


if __name__ == "__main__":
    unittest.main()
