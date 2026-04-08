"""
Configuration validation implementation.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ValidationResult:
    """Result of configuration validation."""

    is_valid: bool
    errors: List[str]
    warnings: List[str]
    applied_defaults: Dict[str, Any]


class ConfigurationValidator:
    """Validates configuration values against schema."""

    _REMOVED_SECTIONS = {"arch_rules", "runtime", "structural_check", "type_check"}

    def __init__(self) -> None:
        self.schema = self._load_schema()
        self.validation_results: List[ValidationResult] = []

    @staticmethod
    def _load_schema() -> Dict[str, Dict[str, Any]]:
        from .schema_data import CONFIGURATION_SCHEMA

        return CONFIGURATION_SCHEMA

    def validate_configuration(
        self, config_dict: Dict[str, Dict[str, Any]]
    ) -> ValidationResult:
        """
        Validate entire configuration dictionary.

        Args:
            config_dict: Configuration to validate

        Returns:
            ValidationResult with validation details
        """
        errors: List[str] = []
        warnings: List[str] = []
        applied_defaults: Dict[str, Any] = {}

        # Validate each section
        for section_name, section_config in config_dict.items():
            if section_name not in self.schema:
                if section_name in self._REMOVED_SECTIONS:
                    errors.append(f"Unknown configuration section: {section_name}")
                    continue
                warnings.append(f"Unknown configuration section: {section_name}")
                continue

            section_errors, section_warnings, section_defaults = self._validate_section(
                section_name, section_config
            )

            errors.extend(error for error in section_errors if error is not None)
            warnings.extend(section_warnings)
            applied_defaults.update(section_defaults)

        # Check for missing required sections
        for section_name in self.schema:
            if section_name not in config_dict:
                section_errors, _, section_defaults = self._validate_section(
                    section_name, {}
                )
                errors.extend(error for error in section_errors if error is not None)
                applied_defaults.update(section_defaults)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            applied_defaults=applied_defaults,
        )

    def _validate_section(
        self, section_name: str, section_config: Dict[str, Any]
    ) -> Tuple[List[Optional[str]], List[str], Dict[str, Any]]:
        """Validate a single configuration section."""
        errors = []
        warnings = []
        applied_defaults = {}

        section_schema = self.schema[section_name]

        # Validate each key in section
        for key_name, value in section_config.items():
            if key_name not in section_schema:
                warnings.append(f"{section_name}.{key_name}: Unknown configuration key")
                continue

            rule = section_schema[key_name]
            is_valid, error_message = rule.validate(value, section_name, key_name)

            if not is_valid:
                errors.append(error_message)

        # Check for missing required keys and apply defaults
        for key_name, rule in section_schema.items():
            if key_name not in section_config:
                if rule.required:
                    errors.append(
                        f"{section_name}.{key_name}: Required configuration key is missing"
                    )
                elif rule.default_value is not None:
                    applied_defaults[f"{section_name}.{key_name}"] = rule.default_value

        return errors, warnings, applied_defaults

    def _is_float(self, value: str) -> bool:
        """Check if string can be converted to float."""
        try:
            float(value)
            return True
        except ValueError:
            return False

    def validate_value(
        self, section: str, key: str, value: Any
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a single configuration value.

        Args:
            section: Configuration section name
            key: Configuration key name
            value: Value to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if section not in self.schema:
            return False, f"Unknown configuration section: {section}"

        if key not in self.schema[section]:
            return False, f"Unknown configuration key: {section}.{key}"

        rule = self.schema[section][key]
        is_valid, error = rule.validate(value, section, key)
        return is_valid, error

    def get_default_value(self, section: str, key: str) -> Any:
        """Get default value for a configuration key."""
        if section not in self.schema or key not in self.schema[section]:
            raise ValueError(f"Unknown configuration key: {section}.{key}")

        return self.schema[section][key].default_value

    def get_schema_info(self, section: Optional[str] = None) -> Dict[str, Any]:
        """
        Get schema information for documentation.

        Args:
            section: Optional section name to filter

        Returns:
            Schema information dictionary
        """
        if section:
            if section not in self.schema:
                raise ValueError(f"Unknown configuration section: {section}")
            return self._format_section_schema(section, self.schema[section])

        return {
            section_name: self._format_section_schema(section_name, section_schema)
            for section_name, section_schema in self.schema.items()
        }

    def _format_section_schema(
        self, section_name: str, section_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format section schema for documentation."""
        formatted = {}

        for key_name, rule in section_schema.items():
            formatted[key_name] = {
                "type": rule.value_type.value,
                "required": rule.required,
                "default": rule.default_value,
                "description": rule.error_message
                or f"Configuration value for {section_name}.{key_name}",
                "constraints": {
                    "min_value": rule.min_value,
                    "max_value": rule.max_value,
                    "min_length": rule.min_length,
                    "max_length": rule.max_length,
                    "allowed_values": rule.allowed_values,
                    "pattern": rule.pattern,
                    "must_exist": rule.must_exist,
                    "must_be_file": rule.must_be_file,
                    "must_be_dir": rule.must_be_dir,
                },
            }

        return formatted


# Global validator instance
validator = ConfigurationValidator()


def validate_configuration(config_dict: Dict[str, Dict[str, Any]]) -> ValidationResult:
    """Validate configuration using global validator."""
    return validator.validate_configuration(config_dict)


def validate_value(section: str, key: str, value: Any) -> Tuple[bool, Optional[str]]:
    """Validate single value using global validator."""
    return validator.validate_value(section, key, value)


def get_schema_info(section: Optional[str] = None) -> Dict[str, Any]:
    """Get schema information using global validator."""
    return validator.get_schema_info(section)
