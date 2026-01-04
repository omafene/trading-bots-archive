#!/usr/bin/env python3
"""
Quick test to verify concurrent trade limit fix
Tests the race condition scenario and validates the fix
"""

import sys
from unittest.mock import Mock, MagicMock
from position_manager_15m import PositionManager15m

class TestConcurrentLimitFix:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def test(self, name, condition, expected=True):
        """Run a test and track results"""
        result = condition == expected
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
        if not result:
            print(f"   Expected: {expected}, Got: {condition}")
            self.failed += 1
        else:
            self.passed += 1
        return result

    def setup_position_manager(self):
        """Create a mock position manager for testing"""
        mock_client = Mock()
        mock_config = {
            'strategy': {
                'order_expiry_seconds': 60
            }
        }
        pm = PositionManager15m(mock_client, mock_config)
        return pm

    def run_all_tests(self):
        print("="*60)
        print("TESTING CONCURRENT TRADE LIMIT FIX")
        print("="*60)
        print()

        # Test 1: get_total_position_count method exists
        print("Test 1: Method Implementation")
        pm = self.setup_position_manager()
        self.test("get_total_position_count() method exists",
                 hasattr(pm, 'get_total_position_count'))

        # Test 2: Count with no positions or orders
        print("\nTest 2: Empty State")
        pm = self.setup_position_manager()
        count = pm.get_total_position_count()
        self.test("Empty state returns 0", count, 0)

        # Test 3: Count with only pending orders (THE CRITICAL FIX)
        print("\nTest 3: Pending Orders Counted (Race Condition Fix)")
        pm = self.setup_position_manager()
        pm.pending_orders = {
            'order_1': {'ticker': 'TEST1'},
            'order_2': {'ticker': 'TEST2'}
        }
        count = pm.get_total_position_count()
        self.test("2 pending orders counted correctly", count, 2)
        print("   ⚠️  OLD BUG: Would return 0 (only counted open_positions)")
        print("   ✅ NEW FIX: Returns 2 (counts pending_orders)")

        # Test 4: Count with only confirmed positions
        print("\nTest 4: Confirmed Positions")
        pm = self.setup_position_manager()
        pm.open_positions = [
            {'ticker': 'POS1', 'count': 100},
            {'ticker': 'POS2', 'count': 50},
            {'ticker': 'POS3', 'count': 75}
        ]
        count = pm.get_total_position_count()
        self.test("3 confirmed positions counted correctly", count, 3)

        # Test 5: Mixed confirmed and pending (REAL WORLD SCENARIO)
        print("\nTest 5: Mixed State (Real World Scenario)")
        pm = self.setup_position_manager()
        pm.open_positions = [
            {'ticker': 'POS1', 'count': 100}
        ]
        pm.pending_orders = {
            'order_1': {'ticker': 'TEST1'},
            'order_2': {'ticker': 'TEST2'}
        }
        count = pm.get_total_position_count()
        self.test("1 confirmed + 2 pending = 3 total", count, 3)

        # Test 6: Simulate the race condition scenario
        print("\nTest 6: Race Condition Scenario Simulation")
        pm = self.setup_position_manager()
        max_concurrent = 3

        # Time T0: No positions, check passes
        count = pm.get_total_position_count()
        can_trade_t0 = count < max_concurrent
        self.test("T0: Empty state allows trading (0 < 3)", can_trade_t0, True)

        # Time T1: Place order 1 (goes to pending)
        pm.pending_orders['order_1'] = {'ticker': 'TEST1'}
        count = pm.get_total_position_count()
        can_trade_t1 = count < max_concurrent
        self.test("T1: After order 1, still can trade (1 < 3)", can_trade_t1, True)
        self.test("T1: Count includes pending order", count, 1)

        # Time T2: Place order 2 (goes to pending)
        pm.pending_orders['order_2'] = {'ticker': 'TEST2'}
        count = pm.get_total_position_count()
        can_trade_t2 = count < max_concurrent
        self.test("T2: After order 2, still can trade (2 < 3)", can_trade_t2, True)
        self.test("T2: Count includes both pending orders", count, 2)

        # Time T3: Place order 3 (goes to pending)
        pm.pending_orders['order_3'] = {'ticker': 'TEST3'}
        count = pm.get_total_position_count()
        can_trade_t3 = count < max_concurrent
        self.test("T3: After order 3, limit reached (3 >= 3)", can_trade_t3, False)
        self.test("T3: Count shows limit reached", count, 3)

        # Time T4: Try to place order 4 - SHOULD BE BLOCKED
        count = pm.get_total_position_count()
        can_trade_t4 = count < max_concurrent
        self.test("T4: Order 4 blocked by limit (3 >= 3)", can_trade_t4, False)
        print("   ✅ RACE CONDITION PREVENTED!")

        # Test 7: Limit enforcement logic (as in edge_bot.py)
        print("\nTest 7: Edge Bot Limit Check Logic")
        pm = self.setup_position_manager()
        pm.pending_orders = {'ord1': {}, 'ord2': {}}
        pm.open_positions = [{'ticker': 'POS1'}]

        max_concurrent = 3
        current_count = pm.get_total_position_count()
        limit_reached = current_count >= max_concurrent

        self.test("Limit check with 1 confirmed + 2 pending", limit_reached, True)
        self.test("Total count matches expected", current_count, 3)

        # Test 8: Verify old bug would have failed
        print("\nTest 8: Verify Old Bug Behavior")
        pm = self.setup_position_manager()
        pm.pending_orders = {'ord1': {}, 'ord2': {}}  # 2 pending orders

        old_count = len(pm.open_positions)  # OLD BUG: only counted this
        new_count = pm.get_total_position_count()  # NEW FIX: counts both

        self.test("Old method would return 0", old_count, 0)
        self.test("New method returns 2", new_count, 2)
        print(f"   🐛 OLD BUG: len(open_positions) = {old_count}")
        print(f"   ✅ NEW FIX: get_total_position_count() = {new_count}")
        print(f"   📊 Difference: {new_count - old_count} positions would have been missed!")

        # Test 9: Edge case - pending order fills during check
        print("\nTest 9: Order Fills During Check")
        pm = self.setup_position_manager()
        pm.pending_orders = {'ord1': {}, 'ord2': {}}
        initial_count = pm.get_total_position_count()

        # Simulate order 1 filling
        pm.pending_orders.pop('ord1')
        pm.open_positions.append({'ticker': 'POS1'})

        new_count = pm.get_total_position_count()
        self.test("Count remains same when pending becomes confirmed",
                 new_count, initial_count)
        print("   ✅ 2 pending → 1 confirmed + 1 pending = still 2 total")

        # Final summary
        print("\n" + "="*60)
        print("TEST RESULTS SUMMARY")
        print("="*60)
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"📊 Total:  {self.passed + self.failed}")
        print()

        if self.failed == 0:
            print("🎉 ALL TESTS PASSED - FIX IS WORKING CORRECTLY!")
            print()
            print("Key Verification:")
            print("  ✅ Pending orders are counted toward limit")
            print("  ✅ Race condition is prevented")
            print("  ✅ Old bug would have allowed limit violations")
            print("  ✅ New fix enforces limit correctly")
            return True
        else:
            print("⚠️  SOME TESTS FAILED - REVIEW NEEDED")
            return False

if __name__ == "__main__":
    tester = TestConcurrentLimitFix()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
