import io
import unittest
from unittest.mock import patch

from owner_access import is_repository_owner


class OwnerAccessTest(unittest.TestCase):
    @patch("owner_access.urlopen")
    @patch("owner_access.subprocess.run")
    def test_only_repository_owner_can_publish(self, credential, urlopen):
        credential.return_value.returncode = 0
        credential.return_value.stdout = "protocol=https\nhost=github.com\npassword=token\n"
        urlopen.return_value = io.BytesIO(b'{"login":"someone-else"}')
        self.assertFalse(is_repository_owner())
        urlopen.return_value = io.BytesIO(b'{"login":"novax1213"}')
        self.assertTrue(is_repository_owner())

    @patch("owner_access.urlopen")
    @patch("owner_access.subprocess.run")
    def test_missing_credential_hides_publisher(self, credential, urlopen):
        credential.return_value.returncode = 1
        credential.return_value.stdout = ""
        self.assertFalse(is_repository_owner())
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
