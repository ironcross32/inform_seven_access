from typing import Any

# ConfigObj sections contain heterogeneous validated values and nested sections.
class ConfigManager:
	spec: dict[str, Any]
	def __getitem__(self, key: str) -> Any: ...

conf: ConfigManager
