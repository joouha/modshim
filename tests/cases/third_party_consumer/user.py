"""A module that imports from third_party_lower and should have imports rewritten."""

from tests.cases.third_party_lower.mod import name as name
from tests.cases.third_party_lower.mod import value

computed = value + 50
