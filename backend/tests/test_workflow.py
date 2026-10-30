import sqlite3
import unittest

from backend import db
from backend.agents.inventory import transfer_preserves_safety, transferable_surplus
from backend.agents.orchestrator import run_disruption_workflow
from backend.agents.planning import days_of_stock, uncovered_quantity


class PlanningCalculationsTests(unittest.TestCase):
    def test_days_of_stock_uses_current_stock_divided_by_daily_demand(self):
        self.assertEqual(days_of_stock(48, 24), 2)

    def test_days_of_stock_handles_missing_zero_demand_and_invalid_values(self):
        self.assertIsNone(days_of_stock(None, 3))
        self.assertIsNone(days_of_stock(12, 0))
        self.assertIsNone(days_of_stock(12, -1))
        self.assertIsNone(days_of_stock(-1, 2))
        self.assertIsNone(days_of_stock(float("inf"), 2))

    def test_uncovered_quantity_and_shortage_inputs(self):
        self.assertEqual(uncovered_quantity(48, 24, 5), 72)
        self.assertEqual(uncovered_quantity(130, 20, 5), 0)
        self.assertIsNone(uncovered_quantity(10, None, 2))
        self.assertIsNone(uncovered_quantity(10, 5, -2))

    def test_transfer_respects_donor_safety_stock(self):
        self.assertEqual(transferable_surplus(132, 60), 72)
        self.assertEqual(transferable_surplus(132, 60, 20), 52)
        self.assertEqual(transferable_surplus(50, 60), 0)
        self.assertTrue(transfer_preserves_safety(132, 60, 72))
        self.assertFalse(transfer_preserves_safety(132, 60, 73))
        self.assertFalse(transfer_preserves_safety(132, 60, 0))


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(db.SCHEMA)
        db._seed_dataset(self.connection)

    def tearDown(self):
        self.connection.close()

    def test_supplier_delay_runs_all_agents_without_executing_actions(self):
        result = run_disruption_workflow(self.connection, "supplier_delay")
        self.assertEqual(result["disruption"]["severity"], "Critical")
        self.assertEqual(result["planning"]["affected_hospitals"], 2)
        self.assertEqual(len(result["agent_steps"]), 5)
        self.assertEqual(len(result["approvals"]), 2)
        self.assertTrue(result["inventory"]["checks"]["safety_stock_enforced"])
        self.assertEqual(
            self.connection.execute("SELECT current_stock FROM inventory WHERE hospital_id='ASTR' AND medicine_id='NOREPI'").fetchone()[0],
            48,
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM shipments WHERE recommendation_id IS NOT NULL").fetchone()[0],
            0,
        )
        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM approvals WHERE decision='pending'").fetchone()[0],
            2,
        )

    def test_allocations_keep_donor_minimums(self):
        result = run_disruption_workflow(self.connection, "supplier_delay")
        proposals = result["inventory"]["recommendations"]
        by_hospital = {item["hospital_id"]: item for item in proposals}
        self.assertEqual(by_hospital["ASTR"]["quantity"], 72)
        self.assertEqual(by_hospital["ASTR"]["donor_hospital_id"], "LAKE")
        self.assertEqual(by_hospital["NORTH"]["quantity"], 15)
        self.assertEqual(by_hospital["NORTH"]["donor_hospital_id"], "COAST")
        self.assertTrue(all(item["details"]["donor_safety_check"] for item in proposals))


if __name__ == "__main__":
    unittest.main()
