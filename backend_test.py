#!/usr/bin/env python3
"""
Cricket Match Simulator Backend API Tests
Tests all backend endpoints for the Cricket Match Simulator app
"""

import requests
import json
import random
from typing import List, Dict, Any

# Backend URL from frontend/.env
BASE_URL = "https://cricketsim-5.preview.emergentagent.com/api"

class CricketAPITester:
    def __init__(self):
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.players = []
        self.test_results = {}
        
    def log_test(self, test_name: str, success: bool, message: str, details: Any = None):
        """Log test results"""
        self.test_results[test_name] = {
            'success': success,
            'message': message,
            'details': details
        }
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if details and not success:
            print(f"   Details: {details}")
    
    def test_players_api(self) -> bool:
        """Test GET /api/players endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/players")
            
            if response.status_code != 200:
                self.log_test("Players API", False, f"HTTP {response.status_code}", response.text)
                return False
            
            players = response.json()
            
            if not isinstance(players, list):
                self.log_test("Players API", False, "Response is not a list", type(players))
                return False
            
            if len(players) < 100:
                self.log_test("Players API", False, f"Expected 100+ players, got {len(players)}")
                return False
            
            # Validate player structure
            sample_player = players[0]
            required_fields = ['id', 'name', 'country', 'role', 'batting', 'bowling']
            missing_fields = [field for field in required_fields if field not in sample_player]
            
            if missing_fields:
                self.log_test("Players API", False, f"Missing fields: {missing_fields}", sample_player)
                return False
            
            # Store players for other tests
            self.players = players
            self.log_test("Players API", True, f"Retrieved {len(players)} players with correct structure")
            return True
            
        except Exception as e:
            self.log_test("Players API", False, f"Exception: {str(e)}")
            return False
    
    def test_quick_simulation(self) -> bool:
        """Test POST /api/matches/quick-sim endpoint"""
        try:
            response = self.session.post(f"{self.base_url}/matches/quick-sim")
            
            if response.status_code != 200:
                self.log_test("Quick Simulation API", False, f"HTTP {response.status_code}", response.text)
                return False
            
            result = response.json()
            
            # The API returns the match result directly, not wrapped in a 'result' field
            # Validate response structure - should have toss, first_innings, second_innings, result
            required_fields = ['toss', 'first_innings', 'second_innings', 'result']
            missing_fields = [field for field in required_fields if field not in result]
            
            if missing_fields:
                self.log_test("Quick Simulation API", False, f"Missing fields: {missing_fields}", list(result.keys()))
                return False
            
            # Check if winner is determined
            if 'winner' not in result['result']:
                self.log_test("Quick Simulation API", False, "No winner determined in result")
                return False
            
            winner = result['result']['winner']
            margin = result['result'].get('margin', 'Unknown margin')
            
            self.log_test("Quick Simulation API", True, f"Match simulated successfully, winner: {winner}, margin: {margin}")
            return True
            
        except Exception as e:
            self.log_test("Quick Simulation API", False, f"Exception: {str(e)}")
            return False
    
    def test_ai_team_generation(self) -> List[str]:
        """Test POST /api/draft/ai-team endpoint"""
        try:
            if not self.players:
                self.log_test("AI Team Generation", False, "No players available for testing")
                return []
            
            # Select 11 random players as user team
            user_team = random.sample([p['id'] for p in self.players], 11)
            
            # The API expects just a list of player IDs, not an object
            response = self.session.post(
                f"{self.base_url}/draft/ai-team",
                json=user_team  # Send as array directly
            )
            
            if response.status_code != 200:
                self.log_test("AI Team Generation", False, f"HTTP {response.status_code}", response.text)
                return []
            
            result = response.json()
            
            # Validate response structure
            if 'player_ids' not in result:
                self.log_test("AI Team Generation", False, "Missing player_ids in response", result.keys())
                return []
            
            ai_team = result['player_ids']
            
            if len(ai_team) != 11:
                self.log_test("AI Team Generation", False, f"Expected 11 players, got {len(ai_team)}")
                return []
            
            # Check no overlap with user team
            overlap = set(user_team) & set(ai_team)
            if overlap:
                self.log_test("AI Team Generation", False, f"AI team overlaps with user team: {overlap}")
                return []
            
            self.log_test("AI Team Generation", True, f"Generated AI team with {len(ai_team)} unique players")
            return ai_team
            
        except Exception as e:
            self.log_test("AI Team Generation", False, f"Exception: {str(e)}")
            return []
    
    def test_batting_order(self, player_ids: List[str]) -> List[str]:
        """Test POST /api/draft/batting-order endpoint"""
        try:
            if len(player_ids) != 11:
                # Use random players if not enough provided
                if not self.players:
                    self.log_test("Batting Order Suggestion", False, "No players available for testing")
                    return []
                player_ids = random.sample([p['id'] for p in self.players], 11)
            
            response = self.session.post(
                f"{self.base_url}/draft/batting-order",
                json=player_ids
            )
            
            if response.status_code != 200:
                self.log_test("Batting Order Suggestion", False, f"HTTP {response.status_code}", response.text)
                return []
            
            result = response.json()
            
            # Validate response structure
            if 'batting_order' not in result:
                self.log_test("Batting Order Suggestion", False, "Missing batting_order in response", result.keys())
                return []
            
            batting_order = result['batting_order']
            
            if len(batting_order) != 11:
                self.log_test("Batting Order Suggestion", False, f"Expected 11 players in order, got {len(batting_order)}")
                return []
            
            # Check all input players are in the order
            if set(player_ids) != set(batting_order):
                self.log_test("Batting Order Suggestion", False, "Batting order doesn't match input players")
                return []
            
            self.log_test("Batting Order Suggestion", True, f"Generated batting order for {len(batting_order)} players")
            return batting_order
            
        except Exception as e:
            self.log_test("Batting Order Suggestion", False, f"Exception: {str(e)}")
            return []
    
    def test_match_simulation(self, team1_ids: List[str], team2_ids: List[str]) -> str:
        """Test POST /api/matches/simulate endpoint"""
        try:
            if len(team1_ids) != 11 or len(team2_ids) != 11:
                self.log_test("Match Simulation API", False, "Both teams must have exactly 11 players")
                return ""
            
            payload = {
                "team1": {
                    "team_name": "Test Team 1",
                    "player_ids": team1_ids
                },
                "team2": {
                    "team_name": "Test Team 2", 
                    "player_ids": team2_ids
                },
                "simulation_mode": "quick"
            }
            
            response = self.session.post(
                f"{self.base_url}/matches/simulate",
                json=payload
            )
            
            if response.status_code != 200:
                self.log_test("Match Simulation API", False, f"HTTP {response.status_code}", response.text)
                return ""
            
            result = response.json()
            
            # Validate response structure
            required_fields = ['match_id', 'result', 'seed']
            missing_fields = [field for field in required_fields if field not in result]
            
            if missing_fields:
                self.log_test("Match Simulation API", False, f"Missing fields: {missing_fields}")
                return ""
            
            # Validate match result
            match_result = result['result']
            if 'result' not in match_result or 'winner' not in match_result['result']:
                self.log_test("Match Simulation API", False, "No winner determined in match result")
                return ""
            
            match_id = result['match_id']
            winner = match_result['result']['winner']
            
            self.log_test("Match Simulation API", True, f"Match simulated successfully, winner: {winner}, match_id: {match_id}")
            return match_id
            
        except Exception as e:
            self.log_test("Match Simulation API", False, f"Exception: {str(e)}")
            return ""
    
    def test_match_history(self, expected_match_id: str = None) -> bool:
        """Test GET /api/matches/history endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/matches/history")
            
            if response.status_code != 200:
                self.log_test("Match History API", False, f"HTTP {response.status_code}", response.text)
                return False
            
            matches = response.json()
            
            if not isinstance(matches, list):
                self.log_test("Match History API", False, "Response is not a list", type(matches))
                return False
            
            if len(matches) == 0:
                self.log_test("Match History API", False, "No matches found in history")
                return False
            
            # Validate match structure
            sample_match = matches[0]
            required_fields = ['id', 'team1_name', 'team2_name', 'winner', 'created_at']
            missing_fields = [field for field in required_fields if field not in sample_match]
            
            if missing_fields:
                self.log_test("Match History API", False, f"Missing fields in match: {missing_fields}")
                return False
            
            # Check if expected match is in history
            if expected_match_id:
                match_ids = [match['id'] for match in matches]
                if expected_match_id not in match_ids:
                    self.log_test("Match History API", False, f"Expected match {expected_match_id} not found in history")
                    return False
            
            self.log_test("Match History API", True, f"Retrieved {len(matches)} matches from history")
            return True
            
        except Exception as e:
            self.log_test("Match History API", False, f"Exception: {str(e)}")
            return False
    
    def run_full_test_suite(self):
        """Run all tests in the recommended order"""
        print("🏏 Starting Cricket Match Simulator Backend API Tests")
        print(f"🌐 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Test 1: Get players (needed for other tests)
        print("\n1️⃣ Testing Players API...")
        players_success = self.test_players_api()
        
        if not players_success:
            print("❌ Cannot continue without player data")
            return self.test_results
        
        # Test 2: Quick simulation
        print("\n2️⃣ Testing Quick Simulation...")
        quick_sim_success = self.test_quick_simulation()
        
        # Test 3: AI team generation
        print("\n3️⃣ Testing AI Team Generation...")
        ai_team = self.test_ai_team_generation()
        ai_team_success = len(ai_team) == 11
        
        # Test 4: Batting order suggestion
        print("\n4️⃣ Testing Batting Order Suggestion...")
        if ai_team_success:
            batting_order = self.test_batting_order(ai_team)
            batting_order_success = len(batting_order) == 11
        else:
            batting_order = self.test_batting_order([])
            batting_order_success = len(batting_order) == 11
        
        # Test 5: Match simulation with custom teams
        print("\n5️⃣ Testing Match Simulation...")
        if ai_team_success and batting_order_success:
            # Use AI team vs random user team
            user_team = random.sample([p['id'] for p in self.players], 11)
            match_id = self.test_match_simulation(user_team, ai_team)
            match_sim_success = bool(match_id)
        else:
            # Use random teams
            team1 = random.sample([p['id'] for p in self.players], 11)
            team2 = random.sample([p['id'] for p in self.players if p['id'] not in team1], 11)
            match_id = self.test_match_simulation(team1, team2)
            match_sim_success = bool(match_id)
        
        # Test 6: Match history
        print("\n6️⃣ Testing Match History...")
        history_success = self.test_match_history(match_id if match_sim_success else None)
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result['success'])
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"{status} {test_name}")
            if not result['success']:
                print(f"   ↳ {result['message']}")
        
        print(f"\n🎯 Results: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("🎉 All tests passed! Backend APIs are working correctly.")
        else:
            print("⚠️  Some tests failed. Check the details above.")
        
        return self.test_results

def main():
    """Main test runner"""
    tester = CricketAPITester()
    results = tester.run_full_test_suite()
    
    # Return exit code based on results
    failed_tests = [name for name, result in results.items() if not result['success']]
    if failed_tests:
        print(f"\n❌ Failed tests: {', '.join(failed_tests)}")
        return 1
    else:
        print("\n✅ All tests passed successfully!")
        return 0

if __name__ == "__main__":
    exit(main())