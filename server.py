from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import random

# Import local modules
from players_data import PLAYERS_DATA, get_all_players, get_player_by_id, get_players_by_country, get_players_by_role
from simulation_engine import SimulationEngine

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="Cricket Match Simulator API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============ Pydantic Models ============

class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

class PlayerResponse(BaseModel):
    id: str
    name: str
    country: str
    role: str
    batting_style: str
    bowling_style: str
    batting: Dict[str, Any]
    bowling: Dict[str, Any]
    era: str

class TeamSetup(BaseModel):
    team_name: str
    player_ids: List[str]  # List of 11 player IDs in batting order

class MatchRequest(BaseModel):
    team1: TeamSetup
    team2: TeamSetup
    seed: Optional[int] = None
    simulation_mode: str = "quick"

class MatchHistoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    team1_name: str
    team2_name: str
    team1_players: List[str]  # Player IDs in batting order
    team2_players: List[str]  # Player IDs in batting order
    team1_score: int
    team2_score: int
    team1_wickets: int
    team2_wickets: int
    team1_overs: float
    team2_overs: float
    winner: str
    margin: str
    toss_winner: str
    toss_decision: str
    first_innings: Dict[str, Any]
    second_innings: Dict[str, Any]
    seed: Optional[int]
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AIDraftRequest(BaseModel):
    user_picks: List[str]  # Player IDs user has picked so far
    difficulty: str = "medium"  # easy, medium, hard
    pick_number: int  # Current pick number (1-11)

class AIDraftResponse(BaseModel):
    player_id: str
    player_name: str
    reasoning: str


# ============ AI Drafting Logic ============

def calculate_player_value(player: Dict, existing_team: List[Dict], difficulty: str) -> float:
    """Calculate a player's value for AI drafting"""
    batting = player.get("batting", {})
    bowling = player.get("bowling", {})
    role = player.get("role", "")
    
    # Base value from stats
    bat_value = batting.get("average", 25) * 0.4 + batting.get("strike_rate", 75) * 0.1
    bowl_value = 0
    if bowling.get("wickets_per_over", 0) > 0:
        bowl_value = (1 / bowling.get("economy", 6)) * 50 + bowling.get("wickets_per_over", 0) * 200
    
    base_value = bat_value + bowl_value
    
    # Role balance bonus
    team_roles = [p.get("role", "") for p in existing_team]
    batsmen_count = sum(1 for r in team_roles if "Batsman" in r or "Wicketkeeper" in r)
    bowlers_count = sum(1 for r in team_roles if r == "Bowler")
    allrounders_count = sum(1 for r in team_roles if "All-rounder" in r)
    wicketkeepers_count = sum(1 for r in team_roles if "Wicketkeeper" in r)
    
    role_bonus = 0
    if "Wicketkeeper" in role and wicketkeepers_count == 0:
        role_bonus = 30  # Need a keeper
    elif "Bowler" == role and bowlers_count < 4:
        role_bonus = 20 + (4 - bowlers_count) * 5  # Need bowlers
    elif "All-rounder" in role and allrounders_count < 2:
        role_bonus = 25  # All-rounders are valuable
    elif ("Batsman" in role or "Wicketkeeper" in role) and batsmen_count < 5:
        role_bonus = 15
    
    # Difficulty adjustments
    if difficulty == "easy":
        # Add randomness, sometimes pick suboptimal
        base_value *= random.uniform(0.6, 1.2)
        role_bonus *= 0.5
    elif difficulty == "hard":
        # More strategic, value scarcity
        if bowl_value > 30:  # Good bowler
            role_bonus += 15  # Death bowlers are scarce
        if batting.get("death_sr", 0) > 110:  # Death overs specialist
            role_bonus += 10
    
    return base_value + role_bonus

def ai_draft_pick(user_picks: List[str], ai_picks: List[str], difficulty: str, all_players: List[Dict]) -> Dict:
    """AI makes a draft pick"""
    # Get available players (not picked by either team)
    picked_ids = set(user_picks + ai_picks)
    available = [p for p in all_players if p["id"] not in picked_ids]
    
    if not available:
        return None
    
    # Get AI's current team
    ai_team = [p for p in all_players if p["id"] in ai_picks]
    
    # Counter-drafting: Look at what user is building
    user_team = [p for p in all_players if p["id"] in user_picks]
    user_roles = [p.get("role", "") for p in user_team]
    
    # Calculate value for each available player
    player_values = []
    for player in available:
        value = calculate_player_value(player, ai_team, difficulty)
        
        # Counter-drafting bonus (hard mode)
        if difficulty == "hard":
            # If user lacks bowlers, grab good bowlers first
            user_bowlers = sum(1 for r in user_roles if r == "Bowler")
            if player.get("role") == "Bowler" and user_bowlers < 3:
                if player.get("bowling", {}).get("wickets_per_over", 0) > 0.08:
                    value += 20  # Grab elite bowlers before user
            
            # If user is building specific country team, diversify
            user_countries = [p.get("country") for p in user_team]
            if user_countries and player.get("country") not in user_countries:
                value += 5  # Slight preference for diversity
        
        player_values.append((player, value))
    
    # Sort by value (descending)
    player_values.sort(key=lambda x: x[1], reverse=True)
    
    # Pick based on difficulty
    if difficulty == "easy":
        # Sometimes pick from top 5 randomly
        top_n = min(5, len(player_values))
        idx = random.randint(0, top_n - 1)
        selected = player_values[idx][0]
    elif difficulty == "medium":
        # Pick from top 3
        top_n = min(3, len(player_values))
        idx = random.randint(0, top_n - 1)
        selected = player_values[idx][0]
    else:  # hard
        # Always pick the best
        selected = player_values[0][0]
    
    # Generate reasoning
    reasons = []
    if "Wicketkeeper" in selected.get("role", ""):
        reasons.append("wicketkeeping option")
    if selected.get("bowling", {}).get("wickets_per_over", 0) > 0.08:
        reasons.append("premium wicket-taker")
    if selected.get("batting", {}).get("average", 0) > 45:
        reasons.append("elite batting average")
    if "All-rounder" in selected.get("role", ""):
        reasons.append("valuable all-round option")
    
    reasoning = f"Selected {selected['name']} - " + (", ".join(reasons) if reasons else "solid team addition")
    
    return {
        "player": selected,
        "reasoning": reasoning
    }

def get_default_batting_order(players: List[Dict]) -> List[str]:
    """Generate a default batting order based on player roles and stats"""
    # Categorize players
    openers = []
    top_order = []
    middle_order = []
    lower_order = []
    tail = []
    
    for p in players:
        role = p.get("role", "")
        batting = p.get("batting", {})
        avg = batting.get("average", 20)
        sr = batting.get("strike_rate", 70)
        powerplay_sr = batting.get("powerplay_sr", 70)
        
        if "Wicketkeeper" in role and powerplay_sr > 90:
            openers.append(p)
        elif ("Batsman" in role or "Wicketkeeper" in role) and powerplay_sr > 85:
            openers.append(p)
        elif ("Batsman" in role or "Wicketkeeper" in role) and avg > 35:
            top_order.append(p)
        elif "All-rounder" in role and avg > 25:
            middle_order.append(p)
        elif "All-rounder" in role:
            lower_order.append(p)
        elif role == "Bowler":
            tail.append(p)
        else:
            middle_order.append(p)
    
    # Sort within categories
    openers.sort(key=lambda x: x.get("batting", {}).get("powerplay_sr", 0), reverse=True)
    top_order.sort(key=lambda x: x.get("batting", {}).get("average", 0), reverse=True)
    middle_order.sort(key=lambda x: x.get("batting", {}).get("average", 0), reverse=True)
    lower_order.sort(key=lambda x: x.get("batting", {}).get("average", 0), reverse=True)
    tail.sort(key=lambda x: x.get("batting", {}).get("average", 0), reverse=True)
    
    # Combine into batting order
    order = []
    order.extend(openers[:2])  # Max 2 openers
    order.extend(top_order[:3])  # Top order
    order.extend(middle_order)  # Middle order
    order.extend(lower_order)  # Lower order
    order.extend(tail)  # Tail
    
    # Ensure we have exactly the players we started with
    remaining = [p for p in players if p not in order]
    order.extend(remaining)
    
    return [p["id"] for p in order[:11]]


# ============ Status Routes ============

@api_router.get("/")
async def root():
    return {"message": "Cricket Match Simulator API", "version": "2.0.0"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.model_dump())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]


# ============ Player Routes ============

@api_router.get("/players", response_model=List[PlayerResponse])
async def get_players(
    country: Optional[str] = None,
    role: Optional[str] = None
):
    """Get all players, optionally filtered by country or role"""
    players = get_all_players()
    
    if country:
        players = [p for p in players if p["country"].lower() == country.lower()]
    
    if role:
        players = [p for p in players if role.lower() in p["role"].lower()]
    
    return players

@api_router.get("/players/{player_id}", response_model=PlayerResponse)
async def get_player(player_id: str):
    """Get a specific player by ID"""
    player = get_player_by_id(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player

@api_router.get("/countries")
async def get_countries():
    """Get list of all countries with player counts"""
    countries = {}
    for player in get_all_players():
        country = player["country"]
        if country not in countries:
            countries[country] = 0
        countries[country] += 1
    
    return [{"name": k, "player_count": v} for k, v in sorted(countries.items())]

@api_router.get("/roles")
async def get_roles():
    """Get list of all player roles"""
    roles = set()
    for player in get_all_players():
        roles.add(player["role"])
    return list(sorted(roles))


# ============ AI Draft Routes ============

@api_router.post("/draft/ai-pick")
async def get_ai_draft_pick(request: AIDraftRequest):
    """Get AI's next draft pick"""
    all_players = get_all_players()
    
    # Calculate how many picks AI has made (alternating draft)
    # If user has picked N, AI has picked N-1 or N (depending on who picks first)
    user_pick_count = len(request.user_picks)
    ai_pick_count = request.pick_number - 1  # AI has made this many picks before this
    
    # For snake draft: AI picks second in odd rounds, first in even rounds
    # Simplified: AI matches user's picks
    
    # Get AI's current picks (we need to track this - for now simulate based on pick number)
    # In a real implementation, this would be stored in session/DB
    
    result = ai_draft_pick(
        user_picks=request.user_picks,
        ai_picks=[],  # This should be tracked - simplified for now
        difficulty=request.difficulty,
        all_players=all_players
    )
    
    if not result:
        raise HTTPException(status_code=400, detail="No players available")
    
    return {
        "player_id": result["player"]["id"],
        "player_name": result["player"]["name"],
        "reasoning": result["reasoning"]
    }

@api_router.post("/draft/ai-team")
async def generate_ai_team(request: dict):
    """Generate a complete AI team given user's team"""
    user_team = request.get("user_team", [])
    difficulty = request.get("difficulty", "medium")
    
    all_players = get_all_players()
    ai_picks = []
    
    # Pick 11 players for AI
    for i in range(11):
        result = ai_draft_pick(
            user_picks=user_team,
            ai_picks=ai_picks,
            difficulty=difficulty,
            all_players=all_players
        )
        if result:
            ai_picks.append(result["player"]["id"])
    
    return {
        "player_ids": ai_picks,
        "players": [get_player_by_id(pid) for pid in ai_picks]
    }

@api_router.post("/draft/ai-single-pick")
async def get_single_ai_pick(request: dict):
    """Get a single AI draft pick for turn-by-turn drafting"""
    user_picks = request.get("user_picks", [])
    ai_picks = request.get("ai_picks", [])
    difficulty = request.get("difficulty", "medium")
    
    all_players = get_all_players()
    
    result = ai_draft_pick(
        user_picks=user_picks,
        ai_picks=ai_picks,
        difficulty=difficulty,
        all_players=all_players
    )
    
    if not result:
        raise HTTPException(status_code=400, detail="No players available")
    
    return {
        "player_id": result["player"]["id"],
        "player": result["player"],
        "reasoning": result["reasoning"]
    }

@api_router.post("/draft/batting-order")
async def get_default_batting_order_route(player_ids: List[str]):
    """Get suggested batting order for a team"""
    players = [get_player_by_id(pid) for pid in player_ids if get_player_by_id(pid)]
    if len(players) != 11:
        raise HTTPException(status_code=400, detail="Must provide exactly 11 players")
    
    order = get_default_batting_order(players)
    return {
        "batting_order": order,
        "players": [get_player_by_id(pid) for pid in order]
    }


# ============ Match Simulation Routes ============

@api_router.post("/matches/simulate")
async def simulate_match(request: MatchRequest):
    """Simulate a complete ODI match"""
    
    # Validate team sizes
    if len(request.team1.player_ids) != 11:
        raise HTTPException(status_code=400, detail="Team 1 must have exactly 11 players")
    if len(request.team2.player_ids) != 11:
        raise HTTPException(status_code=400, detail="Team 2 must have exactly 11 players")
    
    # Get player data for both teams (in batting order)
    team1_players = []
    for pid in request.team1.player_ids:
        player = get_player_by_id(pid)
        if not player:
            raise HTTPException(status_code=404, detail=f"Player not found: {pid}")
        team1_players.append(player)
    
    team2_players = []
    for pid in request.team2.player_ids:
        player = get_player_by_id(pid)
        if not player:
            raise HTTPException(status_code=404, detail=f"Player not found: {pid}")
        team2_players.append(player)
    
    # Create simulation engine
    seed = request.seed if request.seed else random.randint(1, 1000000)
    engine = SimulationEngine(seed=seed)
    
    # Run simulation
    result = engine.simulate_match(
        team1_name=request.team1.team_name,
        team2_name=request.team2.team_name,
        team1_lineup=team1_players,
        team2_lineup=team2_players
    )
    
    # Store match result in database
    match_record = MatchHistoryRecord(
        team1_name=request.team1.team_name,
        team2_name=request.team2.team_name,
        team1_players=request.team1.player_ids,
        team2_players=request.team2.player_ids,
        team1_score=result["first_innings"]["runs"] if result["first_innings"]["batting_team"] == request.team1.team_name else result["second_innings"]["runs"],
        team2_score=result["second_innings"]["runs"] if result["first_innings"]["batting_team"] == request.team1.team_name else result["first_innings"]["runs"],
        team1_wickets=result["first_innings"]["wickets"] if result["first_innings"]["batting_team"] == request.team1.team_name else result["second_innings"]["wickets"],
        team2_wickets=result["second_innings"]["wickets"] if result["first_innings"]["batting_team"] == request.team1.team_name else result["first_innings"]["wickets"],
        team1_overs=result["first_innings"]["overs"] if result["first_innings"]["batting_team"] == request.team1.team_name else result["second_innings"]["overs"],
        team2_overs=result["second_innings"]["overs"] if result["first_innings"]["batting_team"] == request.team1.team_name else result["first_innings"]["overs"],
        winner=result["result"]["winner"],
        margin=result["result"]["margin"],
        toss_winner=result["toss"]["winner"],
        toss_decision=result["toss"]["decision"],
        first_innings=result["first_innings"],
        second_innings=result["second_innings"],
        seed=seed
    )
    
    await db.match_history.insert_one(match_record.model_dump())
    
    return {
        "match_id": match_record.id,
        "result": result,
        "seed": seed,
        "simulation_mode": request.simulation_mode
    }

@api_router.get("/matches/history")
async def get_match_history(limit: int = 50):
    """Get match history"""
    matches = await db.match_history.find().sort("created_at", -1).limit(limit).to_list(limit)
    # Remove _id field for JSON serialization
    for match in matches:
        if "_id" in match:
            del match["_id"]
    return matches

@api_router.get("/matches/history/{match_id}")
async def get_match_from_history(match_id: str):
    """Get a specific match from history"""
    match = await db.match_history.find_one({"id": match_id})
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if "_id" in match:
        del match["_id"]
    return match

@api_router.delete("/matches/history/{match_id}")
async def delete_match_from_history(match_id: str):
    """Delete a match from history"""
    result = await db.match_history.delete_one({"id": match_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Match not found")
    return {"message": "Match deleted"}

@api_router.delete("/matches/history")
async def clear_match_history():
    """Clear all match history"""
    result = await db.match_history.delete_many({})
    return {"message": f"Deleted {result.deleted_count} matches"}


# ============ Quick Simulation Route ============

@api_router.post("/matches/quick-sim")
async def quick_simulate():
    """Run a quick demo simulation with random teams"""
    
    players = get_all_players()
    
    # Create two balanced teams
    batters = [p for p in players if "Batsman" in p["role"] or "Wicketkeeper" in p["role"]]
    allrounders = [p for p in players if "All-rounder" in p["role"]]
    bowlers = [p for p in players if p["role"] == "Bowler"]
    
    random.shuffle(batters)
    random.shuffle(allrounders)
    random.shuffle(bowlers)
    
    # Team 1: 5 batters, 2 all-rounders, 4 bowlers
    team1 = batters[:5] + allrounders[:2] + bowlers[:4]
    team2 = batters[5:10] + allrounders[2:4] + bowlers[4:8]
    
    # Generate batting orders
    team1_order = get_default_batting_order(team1)
    team2_order = get_default_batting_order(team2)
    
    team1_ordered = [get_player_by_id(pid) for pid in team1_order]
    team2_ordered = [get_player_by_id(pid) for pid in team2_order]
    
    seed = random.randint(1, 1000000)
    engine = SimulationEngine(seed=seed)
    
    result = engine.simulate_match(
        team1_name="Dream XI",
        team2_name="Legends XI",
        team1_lineup=team1_ordered,
        team2_lineup=team2_ordered
    )
    
    # Save to history
    match_record = MatchHistoryRecord(
        team1_name="Dream XI",
        team2_name="Legends XI",
        team1_players=team1_order,
        team2_players=team2_order,
        team1_score=result["first_innings"]["runs"] if result["first_innings"]["batting_team"] == "Dream XI" else result["second_innings"]["runs"],
        team2_score=result["second_innings"]["runs"] if result["first_innings"]["batting_team"] == "Dream XI" else result["first_innings"]["runs"],
        team1_wickets=result["first_innings"]["wickets"] if result["first_innings"]["batting_team"] == "Dream XI" else result["second_innings"]["wickets"],
        team2_wickets=result["second_innings"]["wickets"] if result["first_innings"]["batting_team"] == "Dream XI" else result["first_innings"]["wickets"],
        team1_overs=result["first_innings"]["overs"] if result["first_innings"]["batting_team"] == "Dream XI" else result["second_innings"]["overs"],
        team2_overs=result["second_innings"]["overs"] if result["first_innings"]["batting_team"] == "Dream XI" else result["first_innings"]["overs"],
        winner=result["result"]["winner"],
        margin=result["result"]["margin"],
        toss_winner=result["toss"]["winner"],
        toss_decision=result["toss"]["decision"],
        first_innings=result["first_innings"],
        second_innings=result["second_innings"],
        seed=seed
    )
    
    await db.match_history.insert_one(match_record.model_dump())
    
    result["match_id"] = match_record.id
    result["seed"] = seed
    
    return result


# ============ Commentary Routes (LLM-powered) ============

@api_router.post("/commentary/generate")
async def generate_commentary(ball_data: Dict[str, Any]):
    """Generate AI commentary for a ball (using Gemini)"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            return {"commentary": generate_basic_commentary(ball_data)}
        
        chat = LlmChat(
            api_key=api_key,
            session_id=f"cricket-commentary-{uuid.uuid4()}",
            system_message="""You are an expert cricket commentator. Generate brief, engaging commentary (1-2 sentences) for the ball described."""
        ).with_model("gemini", "gemini-3-flash-preview")
        
        prompt = f"""Generate commentary for this ball:
        Batter: {ball_data.get('batter', 'Unknown')}
        Bowler: {ball_data.get('bowler', 'Unknown')}
        Outcome: {ball_data.get('outcome', 'Unknown')}
        Runs: {ball_data.get('runs', 0)}
        Is Wicket: {ball_data.get('is_wicket', False)}
        Score: {ball_data.get('total_after', 0)}/{ball_data.get('wickets_after', 0)}
        """
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        return {"commentary": response}
    
    except Exception as e:
        logger.error(f"Error generating commentary: {e}")
        return {"commentary": generate_basic_commentary(ball_data)}

def generate_basic_commentary(ball_data: Dict[str, Any]) -> str:
    """Generate basic commentary without LLM"""
    outcome = ball_data.get('outcome', 'dot')
    batter = ball_data.get('batter', 'The batter')
    bowler = ball_data.get('bowler', 'the bowler')
    runs = ball_data.get('runs', 0)
    
    if ball_data.get('is_wicket'):
        return f"WICKET! {batter} is dismissed by {bowler}!"
    elif outcome == '6' or outcome == 'SIX':
        return f"SIX! {batter} launches it into the stands!"
    elif outcome == '4' or outcome == 'FOUR':
        return f"FOUR! {batter} finds the boundary!"
    elif outcome == '.' or runs == 0:
        return f"Good delivery from {bowler}, defended by {batter}."
    elif runs == 1:
        return f"Quick single taken by {batter}."
    elif runs == 2:
        return f"Good running, {runs} runs."
    else:
        return f"{batter} faces {bowler}."


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
