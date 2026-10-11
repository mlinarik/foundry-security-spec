"""Recursive transcript redaction before any durable write."""
import re


SECRET_KEYS={'authorization','token','access_token','password','secret','credential','cookie','set-cookie','api_key'}


class Redactor:
    def __init__(self,secrets=()):
        self.secrets=tuple(s for s in secrets if s)

    def redact(self,value):
        if isinstance(value,dict):
            return {k:'[REDACTED]' if k.lower() in SECRET_KEYS else self.redact(v) for k,v in value.items()}
        if isinstance(value,list): return [self.redact(v) for v in value]
        if isinstance(value,str):
            for secret in self.secrets: value=value.replace(secret,'[REDACTED]')
            value=re.sub(r'(?i)bearer\s+[A-Za-z0-9._~+/=-]+','Bearer [REDACTED]',value)
            value=re.sub(r'\b(?:gh[pousr]_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+)\b','[REDACTED]',value)
            return value
        return value
