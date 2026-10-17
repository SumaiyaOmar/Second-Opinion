"""Live connectivity test: python -m unittest discover -s tests -p test_nebius_connection.py"""

import unittest

from core.nebius_client import check_nebius_connection


class NebiusConnectionTest(unittest.TestCase):
    def test_connection(self):
        try:
            response = check_nebius_connection()
        except ValueError:
            self.fail("NEBIUS_API_KEY is missing. Set it in .env before running this test.")
        except Exception as exc:
            # Avoid logging provider error bodies or request credentials.
            self.fail(f"Nebius connectivity check failed ({type(exc).__name__}).")
        print(response)
        self.assertEqual(response, "OK")


if __name__ == "__main__":
    unittest.main()
