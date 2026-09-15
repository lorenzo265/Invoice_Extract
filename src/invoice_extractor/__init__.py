"""Evidence-backed extraction of structured data from PDF invoices."""

from invoice_extractor.domain.models import InvoiceResult
from invoice_extractor.pipeline import extract
from invoice_extractor.profile.loader import load_profile
from invoice_extractor.profile.registry import ProfileRegistry
from invoice_extractor.profile.schema import Profile, ProfileError

__version__ = "0.3.0"

__all__ = [
    "InvoiceResult",
    "Profile",
    "ProfileError",
    "ProfileRegistry",
    "__version__",
    "extract",
    "load_profile",
]
