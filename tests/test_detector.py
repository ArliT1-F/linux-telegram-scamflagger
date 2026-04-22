import unittest

from detector import analyze_message, confidence_label


class DetectorTests(unittest.TestCase):
    def test_high_confidence_message(self):
        text = "OnlyFans premium content. Contact on WhatsApp +1 555 555 5555"
        score, reasons = analyze_message(text)

        self.assertGreaterEqual(score, 60)
        self.assertEqual(confidence_label(score), "HIGH")
        self.assertTrue(any("phone number" in reason for reason in reasons))
        self.assertTrue(any("whatsapp" in reason for reason in reasons))

    def test_low_confidence_message(self):
        score, reasons = analyze_message("Hi, are we still meeting at 6?")
        self.assertLess(score, 30)
        self.assertEqual(confidence_label(score), "LOW")
        self.assertEqual(reasons, [])


if __name__ == "__main__":
    unittest.main()
