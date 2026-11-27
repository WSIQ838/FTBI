from unittest import TestCase
from unittest.mock import patch
from urllib.request import Request
from scripts.load_probe import LocalRedirects,percentile,validate,run


class LoadProbeTests(TestCase):
    def test_guard_requires_explicit_opt_in_and_bounded_synthetic_fixture(self):
        with patch.dict("os.environ",{},clear=True):
            with self.assertRaises(ValueError): validate(8766,120,10000)
        with patch.dict("os.environ",{"FTBI_LOAD_TESTING":"1","FTBI_DEMO_PASSWORD":"synthetic-password-only"}):
            validate(8766,120,10000)
            for port,requests,limit in [(80,120,10000),(8766,10000,10000),(8766,120,30000)]:
                with self.assertRaises(ValueError): validate(port,requests,limit)

    def test_redirect_cannot_send_session_to_another_origin(self):
        for origin in ["https://example.com","http://localhost:8766","http://127.0.0.1:8766/path"]:
            with self.assertRaises(ValueError): LocalRedirects(origin)
        handler=LocalRedirects("http://127.0.0.1:8766")
        with self.assertRaises(ValueError): handler.redirect_request(Request("http://127.0.0.1:8766/"),None,302,"",{},"https://example.com/")
        with self.assertRaises(ValueError): handler.redirect_request(Request("http://127.0.0.1:8766/"),None,302,"",{},"http://127.0.0.1:8767/")

    def test_percentiles_and_http_failure_fail_the_gate(self):
        self.assertEqual(percentile([4,1,3,2],.5),2)
        self.assertEqual(percentile([4,1,3,2],.95),4)
        with patch("scripts.load_probe.build_opener",side_effect=OSError("synthetic failure")):
            report=run("http://127.0.0.1:8766","synthetic-cookie","/courses/1/",12,10000)
        self.assertFalse(report["accepted"])
        self.assertEqual([stage["failures"] for stage in report["stages"]],[12,12,12])
        self.assertNotIn("synthetic-cookie",str(report))
