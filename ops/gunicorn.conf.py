# Access logs intentionally exclude URL paths, queries, IPs, cookies and headers.
access_log_format='{"status":"%(s)s","duration_us":"%(D)s","bytes":"%(B)s"}'
logconfig_dict={
    "version":1,"disable_existing_loggers":False,
    "formatters":{"safe":{"()":"ftbi.observability.SafeJSONFormatter"},"access":{"format":"%(message)s"}},
    "handlers":{"error":{"class":"logging.StreamHandler","formatter":"safe"},"access":{"class":"logging.StreamHandler","formatter":"access"}},
    "loggers":{"gunicorn.error":{"handlers":["error"],"level":"INFO","propagate":False},"gunicorn.access":{"handlers":["access"],"level":"INFO","propagate":False}},
}
