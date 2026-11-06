import unittest

from smartgrid.contracts import PROJECT_CONTRACT, ProjectContract


class ProjectContractTests(unittest.TestCase):
    def test_official_dimensions(self) -> None:
        self.assertEqual(PROJECT_CONTRACT.context_steps, 672)
        self.assertEqual(PROJECT_CONTRACT.input_feature_count, 11)
        self.assertEqual(len(PROJECT_CONTRACT.target_features), 4)

    def test_canonical_columns_keep_timestamp_and_four_electrical_values(self) -> None:
        self.assertEqual(
            PROJECT_CONTRACT.canonical_columns,
            ("timestamp", "Ea", "Er", "Pmax", "Smax"),
        )

    def test_contract_rejects_inconsistent_cadence(self) -> None:
        invalid = ProjectContract(cadence_minutes=30)
        with self.assertRaisesRegex(ValueError, "cadence_minutes"):
            invalid.validate()

    def test_contract_rejects_wrong_calendar_feature_count(self) -> None:
        invalid = ProjectContract(calendar_feature_count=6)
        with self.assertRaisesRegex(ValueError, "11 features"):
            invalid.validate()


if __name__ == "__main__":
    unittest.main()
