"""
Cricket Match Simulation Engine v3
A probabilistic ball-by-ball simulation engine for ODI cricket matches.

PRD v3 Features:
- Confidence & Pressure system with player-specific responses
- Batting role effects (Anchor/Balanced/Aggressive)
- Dynamic strike rate modifiers (position, bowling quality)
- Simplified team fielding modifier
- Mandatory randomness injection (anti-determinism)
- Data scope limitation (Top 20 vs Archetype players)

All outcomes are probabilistic - no scripted results, no hard caps.
"""

import random
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class MatchPhase(Enum):
    POWERPLAY = "powerplay"  # Overs 1-10
    MIDDLE = "middle"        # Overs 11-40
    DEATH = "death"          # Overs 41-50


class BattingRole(Enum):
    ANCHOR = "anchor"        # Lower dismissal risk, conservative
    BALANCED = "balanced"    # Neutral
    AGGRESSIVE = "aggressive"  # Higher dismissal risk, attacking


class PressureResponse(Enum):
    THRIVES = "thrives"      # Performs better under pressure
    NEUTRAL = "neutral"      # Minimal effect
    CRUMBLES = "crumbles"    # Performs worse under pressure


class BallOutcome(Enum):
    DOT = 0
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    SIX = 6
    WICKET = -1
    WIDE = "wide"
    NO_BALL = "no_ball"


# Top 60 elite players who get full statistical modeling
ELITE_PLAYERS = {
    # Top 20 Batters
    "sachin_tendulkar", "virat_kohli", "ricky_ponting", "ab_de_villiers", 
    "viv_richards", "brian_lara", "rohit_sharma", "kumar_sangakkara",
    "hashim_amla", "babar_azam", "joe_root", "steve_smith", 
    "kane_williamson", "david_warner", "chris_gayle", "ms_dhoni",
    "adam_gilchrist", "sanath_jayasuriya", "matthew_hayden", "jacques_kallis",
    # Top 20 Bowlers
    "wasim_akram", "glenn_mcgrath", "muttiah_muralitharan", "shane_warne",
    "mitchell_starc", "jasprit_bumrah", "dale_steyn", "curtly_ambrose",
    "waqar_younis", "brett_lee", "lasith_malinga", "trent_boult",
    "pat_cummins", "kagiso_rabada", "rashid_khan", "shaheen_afridi",
    "joel_garner", "malcolm_marshall", "james_anderson", "stuart_broad",
    # Top 20 All-rounders
    "imran_khan", "kapil_dev", "ian_botham", "richard_hadlee",
    "ravindra_jadeja", "ben_stokes", "shakib_al_hasan", "andrew_flintoff",
    "lance_klusener", "chris_cairns", "shaun_pollock", "daniel_vettori",
    "yuvraj_singh", "hardik_pandya", "jason_holder", "ravichandran_ashwin",
    "kieron_pollard", "dwayne_bravo", "shahid_afridi", "abdul_razzaq"
}


@dataclass
class BatterState:
    player: Dict
    runs: int = 0
    balls_faced: int = 0
    fours: int = 0
    sixes: int = 0
    is_out: bool = False
    dismissal_type: str = ""
    dismissed_by: str = ""
    confidence: float = 0.7  # Starts low, builds as batter settles
    current_pressure: float = 0.0  # Dynamic pressure level

    @property
    def strike_rate(self) -> float:
        if self.balls_faced == 0:
            return 0.0
        return (self.runs / self.balls_faced) * 100
    
    @property
    def is_set(self) -> bool:
        """A batter is 'set' after facing 20+ balls with decent runs"""
        return self.balls_faced >= 20 and self.runs >= 10


@dataclass
class BowlerState:
    player: Dict
    overs: float = 0
    balls_bowled: int = 0
    runs_conceded: int = 0
    wickets: int = 0
    maidens: int = 0
    extras: int = 0
    current_over_runs: int = 0
    dots_in_current_over: int = 0
    fatigue: float = 0.0  # Increases as bowler bowls more
    spell_balls: int = 0  # Balls in current spell

    @property
    def economy(self) -> float:
        if self.overs == 0:
            return 0.0
        return self.runs_conceded / self.overs if self.overs > 0 else 0
    
    @property
    def current_spell_overs(self) -> float:
        return self.spell_balls / 6


@dataclass
class InningsState:
    batting_team: str
    bowling_team: str
    batting_lineup: List[Dict]
    bowling_lineup: List[Dict]
    runs: int = 0
    wickets: int = 0
    overs: float = 0
    balls: int = 0
    extras: int = 0
    target: Optional[int] = None
    batters: List[BatterState] = field(default_factory=list)
    bowlers: List[BowlerState] = field(default_factory=list)
    striker_idx: int = 0
    non_striker_idx: int = 1
    current_bowler_idx: int = 0
    fall_of_wickets: List[Dict] = field(default_factory=list)
    ball_log: List[Dict] = field(default_factory=list)
    momentum: float = 0.0  # -1 to 1, negative = bowling dominant
    team_fielding_modifier: float = 1.0  # Simplified fielding effect
    match_pressure: float = 0.0  # Overall match pressure (0-1)

    @property
    def current_run_rate(self) -> float:
        if self.overs == 0:
            return 0.0
        return self.runs / self.overs

    @property
    def required_run_rate(self) -> Optional[float]:
        if self.target is None:
            return None
        remaining_runs = self.target - self.runs
        overs_completed = int(self.overs)
        balls_in_current_over = self.balls % 6
        remaining_overs = 50 - overs_completed - (balls_in_current_over / 6)
        if remaining_overs <= 0:
            return None
        return remaining_runs / remaining_overs

    @property
    def projected_score(self) -> float:
        """Project final score based on current run rate"""
        if self.overs < 5:
            return self.runs * 10
        return self.current_run_rate * 50

    @property
    def phase(self) -> MatchPhase:
        over = int(self.overs)
        if over < 10:
            return MatchPhase.POWERPLAY
        elif over < 40:
            return MatchPhase.MIDDLE
        else:
            return MatchPhase.DEATH


class SimulationEngine:
    """
    Statistical Cricket Simulation Engine v3
    
    Key Principles (from PRD):
    - No scripted outcomes
    - No hard caps
    - No single-factor dominance
    - Mandatory randomness on every ball
    - Star players dominate on average, not always
    """
    
    # Score distribution targets
    SCORE_PERCENTILES = {
        25: 235,   # Below average day
        50: 275,   # Median ODI score
        75: 315,   # Good performance
        90: 350,   # Excellent performance
        95: 385,   # Exceptional
        99: 420,   # Historical best
    }
    
    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        if seed is not None:
            random.seed(seed)
    
    # ==================== PLAYER TRAIT EXTRACTION ====================
    
    def is_elite_player(self, player: Dict) -> bool:
        """Check if player is in the top 60 with full statistical profiles"""
        player_id = player.get("id", "").lower().replace(" ", "_")
        return player_id in ELITE_PLAYERS
    
    def get_batting_role(self, player: Dict) -> BattingRole:
        """Determine batting role from player data"""
        role = player.get("batting_role", "").lower()
        batting = player.get("batting", {})
        
        if "anchor" in role or batting.get("strike_rate", 80) < 75:
            return BattingRole.ANCHOR
        elif "aggressive" in role or "hitter" in role or batting.get("strike_rate", 80) > 95:
            return BattingRole.AGGRESSIVE
        else:
            return BattingRole.BALANCED
    
    def get_pressure_response(self, player: Dict) -> PressureResponse:
        """Get player's response to pressure situations"""
        # Use pressure_factor from player data, or default based on experience
        pressure_factor = player.get("batting", {}).get("pressure_factor", 0.85)
        
        if pressure_factor >= 0.95:
            return PressureResponse.THRIVES
        elif pressure_factor >= 0.80:
            return PressureResponse.NEUTRAL
        else:
            return PressureResponse.CRUMBLES
    
    def get_preferred_batting_position(self, player: Dict) -> int:
        """Get player's preferred batting position (1-11)"""
        return player.get("batting", {}).get("preferred_position", 5)
    
    # ==================== CONFIDENCE & PRESSURE MODIFIERS ====================
    
    def calculate_confidence(self, batter_state: BatterState) -> float:
        """
        Calculate batter confidence based on their current innings.
        Confidence affects both dismissal likelihood AND scoring.
        
        Returns: 0.5 (very nervous) to 1.3 (very confident)
        """
        balls = batter_state.balls_faced
        runs = batter_state.runs
        
        # Base confidence builds with balls faced
        if balls < 5:
            base = 0.7  # Very nervous start
        elif balls < 15:
            base = 0.8 + (balls / 100)  # Building
        elif balls < 30:
            base = 0.9 + (balls / 150)  # Settling
        elif balls < 60:
            base = 1.0 + (runs / 300)  # Set
        else:
            # Very set, but fatigue starts
            base = 1.1 + (runs / 400) - (balls / 800)
        
        # Boost from scoring (runs build confidence)
        run_boost = min(0.15, runs / 500)
        
        # Boundary boost (hitting boundaries feels good)
        boundary_boost = min(0.1, (batter_state.fours + batter_state.sixes * 1.5) / 50)
        
        confidence = base + run_boost + boundary_boost
        
        # Clamp between 0.5 and 1.3
        return max(0.5, min(1.3, confidence))
    
    def calculate_match_pressure(self, innings: InningsState, match_situation: Dict) -> float:
        """
        Calculate overall match pressure (0-1).
        Higher pressure affects batters differently based on their pressure response.
        """
        pressure = 0.0
        
        # Wickets down pressure
        pressure += innings.wickets * 0.08  # Max 0.8 from wickets
        
        # Chase pressure
        if match_situation.get("chasing"):
            required_rr = match_situation.get("required_run_rate", 6)
            current_rr = match_situation.get("current_run_rate", 6)
            
            if required_rr > current_rr + 4:
                pressure += 0.4  # Heavy pressure
            elif required_rr > current_rr + 2:
                pressure += 0.25
            elif required_rr > current_rr:
                pressure += 0.1
            
            # Final overs pressure
            overs_remaining = match_situation.get("overs_remaining", 50)
            if overs_remaining < 10:
                pressure += (10 - overs_remaining) * 0.03
        
        # Setting a total pressure (need to accelerate)
        if not match_situation.get("chasing") and innings.phase == MatchPhase.DEATH:
            pressure += 0.15
        
        return min(1.0, pressure)
    
    def apply_pressure_to_batter(self, base_dismissal: float, batter: Dict, 
                                  batter_state: BatterState, pressure: float) -> float:
        """
        Apply pressure modifier to dismissal probability based on player's pressure response.
        
        Returns: Modified dismissal probability
        """
        response = self.get_pressure_response(batter)
        confidence = self.calculate_confidence(batter_state)
        
        if response == PressureResponse.THRIVES:
            # Pressure actually helps - dismissal decreases
            modifier = 1.0 - (pressure * 0.15)
        elif response == PressureResponse.NEUTRAL:
            # Minimal effect
            modifier = 1.0 + (pressure * 0.05)
        else:  # CRUMBLES
            # Pressure hurts - dismissal increases
            modifier = 1.0 + (pressure * 0.35)
        
        # Compound with confidence (low confidence + high pressure = danger)
        if confidence < 0.8 and pressure > 0.5:
            modifier *= 1.2  # Compounding effect
        
        return base_dismissal * modifier
    
    # ==================== BATTING ROLE MODIFIERS ====================
    
    def get_role_dismissal_modifier(self, role: BattingRole) -> float:
        """
        Get dismissal probability modifier based on batting role.
        
        Anchor: Lower baseline dismissal risk
        Balanced: Neutral
        Aggressive/Hitter: Higher baseline dismissal risk
        """
        if role == BattingRole.ANCHOR:
            return 0.75  # 25% less likely to get out
        elif role == BattingRole.AGGRESSIVE:
            return 1.3   # 30% more likely to get out
        else:
            return 1.0   # Neutral
    
    def get_role_scoring_modifier(self, role: BattingRole, confidence: float) -> Dict[str, float]:
        """
        Get scoring modifiers based on batting role.
        Returns modifiers for boundaries and strike rate.
        """
        if role == BattingRole.ANCHOR:
            return {
                "boundary_mod": 0.8,  # Fewer boundaries
                "sr_mod": 0.85,       # Lower strike rate
                "dot_mod": 1.1        # More dots (consolidation)
            }
        elif role == BattingRole.AGGRESSIVE:
            # Aggressive players swing harder, especially when confident
            boundary_boost = 1.0 + (confidence - 0.8) * 0.3 if confidence > 0.8 else 1.0
            return {
                "boundary_mod": 1.25 * boundary_boost,
                "sr_mod": 1.15,
                "dot_mod": 0.9
            }
        else:
            return {
                "boundary_mod": 1.0,
                "sr_mod": 1.0,
                "dot_mod": 1.0
            }
    
    # ==================== POSITION EFFECTS ====================
    
    def get_position_modifier(self, batter: Dict, actual_position: int) -> Dict[str, float]:
        """
        Get modifiers based on how far batter is from preferred position.
        
        Out of position batters:
        - Have reduced strike rate
        - Slightly increased dismissal risk (from uncomfortable shots)
        """
        preferred = self.get_preferred_batting_position(batter)
        position_diff = abs(actual_position - preferred)
        
        if position_diff == 0:
            return {"sr_mod": 1.0, "dismissal_mod": 1.0}
        elif position_diff <= 2:
            # Slightly out of position
            return {"sr_mod": 0.92, "dismissal_mod": 1.08}
        else:
            # Completely out of position
            return {"sr_mod": 0.82, "dismissal_mod": 1.2}
    
    # ==================== BOWLING QUALITY EFFECTS ====================
    
    def get_bowling_quality_modifier(self, bowler: Dict, phase: MatchPhase) -> Dict[str, float]:
        """
        High quality bowling reduces batter effectiveness.
        This applies regardless of batter quality.
        """
        bowling = bowler.get("bowling", {})
        economy = bowling.get("economy", 5.0)
        strike_rate = bowling.get("strike_rate", 35)
        
        # Quality score based on economy and strike rate
        quality = 0.5
        if economy < 4.5:
            quality += 0.2
        elif economy < 5.5:
            quality += 0.1
        
        if strike_rate < 30:
            quality += 0.2
        elif strike_rate < 40:
            quality += 0.1
        
        # Phase-specific effectiveness
        if phase == MatchPhase.POWERPLAY:
            phase_eff = bowling.get("powerplay_eff", 0.85)
        elif phase == MatchPhase.DEATH:
            phase_eff = bowling.get("death_eff", 0.85)
        else:
            phase_eff = 0.85
        
        quality *= phase_eff
        
        # High quality bowling effects
        if quality > 0.9:
            return {
                "sr_reduction": 0.82,      # Significant SR reduction
                "dot_increase": 1.25,      # More dots
                "boundary_reduction": 0.75 # Fewer boundaries
            }
        elif quality > 0.7:
            return {
                "sr_reduction": 0.9,
                "dot_increase": 1.12,
                "boundary_reduction": 0.88
            }
        else:
            return {
                "sr_reduction": 1.0,
                "dot_increase": 1.0,
                "boundary_reduction": 1.0
            }
    
    # ==================== TEAM FIELDING (SIMPLIFIED) ====================
    
    def calculate_team_fielding_modifier(self, bowling_lineup: List[Dict]) -> float:
        """
        Calculate a single team fielding score.
        This is a MINOR modifier, never decisive.
        
        Returns: 0.95 (poor fielding, slight batting boost) to 1.05 (good fielding, slight batting nerf)
        """
        total_fielding = 0
        count = 0
        
        for player in bowling_lineup:
            fielding = player.get("fielding", {}).get("rating", 75)
            total_fielding += fielding
            count += 1
        
        if count == 0:
            return 1.0
        
        avg_fielding = total_fielding / count
        
        # Minor modifier only
        if avg_fielding > 82:
            return 1.03  # Good fielding - slight batting nerf
        elif avg_fielding < 68:
            return 0.97  # Poor fielding - slight batting boost
        else:
            return 1.0
    
    # ==================== MANDATORY RANDOMNESS ====================
    
    def inject_noise(self, base_value: float, noise_magnitude: float = 0.1, 
                     pressure: float = 0, aggression: float = 0, 
                     confidence: float = 1.0) -> float:
        """
        Inject mandatory randomness into any probability.
        
        PRD: "Every ball must include a noise term"
        
        Noise is larger under:
        - High pressure
        - High aggression
        - Low confidence
        """
        # Base noise
        noise_factor = noise_magnitude
        
        # Increase noise under pressure
        noise_factor += pressure * 0.08
        
        # Increase noise for aggressive players
        noise_factor += aggression * 0.05
        
        # Increase noise with low confidence
        if confidence < 0.8:
            noise_factor += (0.8 - confidence) * 0.15
        
        # Generate random noise
        noise = random.gauss(0, noise_factor)
        
        return base_value * (1 + noise)
    
    def should_upset_occur(self, base_probability: float = 0.05) -> bool:
        """
        Check if an upset should occur (good batter out early, star bowler goes for runs).
        
        PRD: "Cricket must remain probabilistic"
        """
        return random.random() < base_probability
    
    # ==================== MATCHUP CALCULATIONS ====================
    
    def calculate_matchup_factor(self, batter: Dict, bowler: Dict) -> float:
        """Calculate how well a batter matches up against a bowler"""
        batting = batter.get("batting", {})
        bowling = bowler.get("bowling", {})
        
        # Pace vs Spin matchup
        bowler_type = bowler.get("bowling_type", "pace").lower()
        
        if "spin" in bowler_type:
            batter_vs_spin = batting.get("vs_spin", 0.85)
            base_matchup = batter_vs_spin
        else:
            batter_vs_pace = batting.get("vs_pace", 0.85)
            base_matchup = batter_vs_pace
        
        return base_matchup
    
    # ==================== PHASE MODIFIERS ====================
    
    def get_phase_strike_rate(self, batter: Dict, phase: MatchPhase) -> float:
        """Get batter's strike rate for current phase"""
        batting = batter.get("batting", {})
        base_sr = batting.get("strike_rate", 80)
        
        if phase == MatchPhase.POWERPLAY:
            sr = batting.get("powerplay_sr", base_sr)
            return sr * 0.88
        elif phase == MatchPhase.MIDDLE:
            sr = batting.get("middle_sr", base_sr)
            return sr * 0.82
        else:
            sr = batting.get("death_sr", base_sr)
            return sr * 0.90
    
    def get_bowler_effectiveness(self, bowler: Dict, phase: MatchPhase, fatigue: float) -> float:
        """Get bowler's effectiveness for current phase with fatigue"""
        bowling = bowler.get("bowling", {})
        
        if phase == MatchPhase.POWERPLAY:
            base_eff = bowling.get("powerplay_eff", 0.85)
        elif phase == MatchPhase.MIDDLE:
            base_eff = (bowling.get("powerplay_eff", 0.85) + bowling.get("death_eff", 0.85)) / 2
        else:
            base_eff = bowling.get("death_eff", 0.85)
        
        # Fatigue reduces effectiveness
        fatigue_penalty = fatigue * 0.25
        return max(0.5, base_eff - fatigue_penalty)
    
    # ==================== DISMISSAL PROBABILITY (FULL MODEL) ====================
    
    def calculate_dismissal_probability(
        self,
        batter: Dict,
        batter_state: BatterState,
        bowler: Dict,
        bowler_state: BowlerState,
        phase: MatchPhase,
        match_situation: Dict,
        innings: InningsState,
        actual_position: int
    ) -> float:
        """
        Calculate dismissal probability per ball using full dependency model.
        
        PRD: Dismissal probability must be a function of:
        - Batting average (contextual)
        - Bowling average & strike rate (phase-adjusted)
        - Batting role (anchor vs hitter)
        - Confidence (higher → less likely)
        - Pressure (player-specific response)
        - Fatigue
        - Match phase
        - Matchups
        - Team fielding
        - Random noise
        
        No single factor may dominate.
        """
        batting = batter.get("batting", {})
        bowling = bowler.get("bowling", {})
        
        # === BASE PROBABILITY ===
        # Start from bowler's wicket-taking ability
        base_wicket_rate = bowling.get("wickets_per_over", 0.08) / 6  # Per ball
        base_dismissal = max(0.01, min(0.15, base_wicket_rate))
        
        # === BATTING SKILL MODIFIER ===
        batter_avg = batting.get("average", 35)
        batting_skill = 1.0 - min(0.4, (batter_avg - 30) / 100)  # Higher avg = lower dismissal
        
        # === BOWLING SKILL MODIFIER ===
        bowler_sr = bowling.get("strike_rate", 35)
        bowling_skill = 1.0 + min(0.3, (40 - bowler_sr) / 100)  # Lower SR = higher dismissal
        
        # === MATCHUP MODIFIER ===
        matchup = self.calculate_matchup_factor(batter, bowler)
        matchup_mod = 2.0 - matchup  # Lower matchup skill = higher dismissal
        
        # === ROLE MODIFIER ===
        role = self.get_batting_role(batter)
        role_mod = self.get_role_dismissal_modifier(role)
        
        # === POSITION MODIFIER ===
        position_mods = self.get_position_modifier(batter, actual_position)
        position_mod = position_mods["dismissal_mod"]
        
        # === CONFIDENCE MODIFIER ===
        confidence = self.calculate_confidence(batter_state)
        confidence_mod = 1.3 - (confidence * 0.4)  # Higher confidence = lower dismissal
        
        # === PRESSURE MODIFIER (Player-specific) ===
        pressure = self.calculate_match_pressure(innings, match_situation)
        # This applies the player's specific pressure response
        pressure_modifier = 1.0  # Will be applied separately
        
        # === FATIGUE MODIFIER ===
        bowler_fatigue = bowler_state.fatigue
        batter_fatigue = batter_state.balls_faced / 150  # Batter fatigue from long innings
        fatigue_mod = 1.0 + (batter_fatigue * 0.2) - (bowler_fatigue * 0.1)
        
        # === PHASE MODIFIER ===
        if phase == MatchPhase.POWERPLAY:
            phase_mod = 0.85  # Fewer wickets in powerplay (field restrictions)
        elif phase == MatchPhase.DEATH:
            phase_mod = 1.15  # More wickets in death (risks taken)
        else:
            phase_mod = 1.0
        
        # === TEAM FIELDING MODIFIER ===
        fielding_mod = innings.team_fielding_modifier
        
        # === COMPOSE PROBABILITY ===
        dismissal = (
            base_dismissal
            * batting_skill
            * bowling_skill
            * matchup_mod
            * role_mod
            * position_mod
            * confidence_mod
            * fatigue_mod
            * phase_mod
            * fielding_mod
        )
        
        # Apply pressure (player-specific response)
        dismissal = self.apply_pressure_to_batter(dismissal, batter, batter_state, pressure)
        
        # === INJECT MANDATORY NOISE ===
        aggression = 0.5 if role == BattingRole.AGGRESSIVE else 0.2
        dismissal = self.inject_noise(
            dismissal, 
            noise_magnitude=0.12,
            pressure=pressure,
            aggression=aggression,
            confidence=confidence
        )
        
        # === UPSET CHANCE (Anti-determinism) ===
        # Even set batters can get out, even new batters can survive
        if batter_state.is_set and self.should_upset_occur(0.02):
            dismissal *= 2.5  # Set batter has a bad ball
        elif batter_state.balls_faced < 5 and self.should_upset_occur(0.15):
            dismissal *= 0.3  # New batter survives a tough delivery
        
        # Final clamp - never guarantee survival or dismissal
        return max(0.008, min(0.12, dismissal))
    
    # ==================== BALL PROBABILITY CALCULATION ====================
    
    def calculate_ball_probabilities(
        self,
        batter: Dict,
        batter_state: BatterState,
        bowler: Dict,
        bowler_state: BowlerState,
        phase: MatchPhase,
        match_situation: Dict,
        innings: InningsState,
        actual_position: int = 5
    ) -> Dict[str, float]:
        """
        Calculate probabilities for each ball outcome.
        Uses full dependency model with mandatory randomness.
        """
        batting = batter.get("batting", {})
        bowling = bowler.get("bowling", {})
        
        # === GET ALL MODIFIERS ===
        confidence = self.calculate_confidence(batter_state)
        pressure = self.calculate_match_pressure(innings, match_situation)
        role = self.get_batting_role(batter)
        role_mods = self.get_role_scoring_modifier(role, confidence)
        position_mods = self.get_position_modifier(batter, actual_position)
        bowling_quality = self.get_bowling_quality_modifier(bowler, phase)
        matchup = self.calculate_matchup_factor(batter, bowler)
        bowler_eff = self.get_bowler_effectiveness(bowler, phase, bowler_state.fatigue)
        
        # Base strike rate (phase-adjusted)
        batter_sr = self.get_phase_strike_rate(batter, phase) / 100
        
        # Apply modifiers to strike rate
        effective_sr = (
            batter_sr 
            * role_mods["sr_mod"]
            * position_mods["sr_mod"]
            * bowling_quality["sr_reduction"]
            * matchup
            * (0.5 + confidence * 0.5)  # Confidence effect
        )
        
        # === WICKET PROBABILITY ===
        wicket_prob = self.calculate_dismissal_probability(
            batter, batter_state, bowler, bowler_state,
            phase, match_situation, innings, actual_position
        )
        
        # === DOT BALL PROBABILITY ===
        bowler_dot_rate = bowling.get("dot_ball_pct", 0.40)
        dot_base = 0.38 + (bowler_dot_rate - 0.40) * 0.5
        dot_prob = (
            dot_base 
            * role_mods["dot_mod"]
            * bowling_quality["dot_increase"]
            * bowler_eff
            / (matchup * 0.5 + 0.5)
        )
        dot_prob = self.inject_noise(dot_prob, 0.08, pressure, confidence=confidence)
        dot_prob = max(0.25, min(0.55, dot_prob))
        
        # === BOUNDARY PROBABILITIES ===
        four_base = effective_sr * 0.10 * matchup * role_mods["boundary_mod"]
        six_base = effective_sr * 0.035 * matchup * role_mods["boundary_mod"]
        
        # Apply bowling quality reduction
        four_base *= bowling_quality["boundary_reduction"]
        six_base *= bowling_quality["boundary_reduction"]
        
        # Phase adjustments
        if phase == MatchPhase.POWERPLAY:
            four_base *= 1.15
            six_base *= 0.85
        elif phase == MatchPhase.DEATH:
            four_base *= 1.1
            six_base *= 1.25
        
        # Inject noise
        four_prob = self.inject_noise(four_base, 0.1, pressure, 
                                       0.3 if role == BattingRole.AGGRESSIVE else 0.1, confidence)
        six_prob = self.inject_noise(six_base, 0.12, pressure,
                                      0.4 if role == BattingRole.AGGRESSIVE else 0.1, confidence)
        
        four_prob = max(0.04, min(0.16, four_prob))
        six_prob = max(0.015, min(0.08, six_prob))
        
        # === EXTRAS ===
        extras_prob = 0.025
        
        # === RUNNING (from remaining probability) ===
        remaining = 1 - dot_prob - wicket_prob - four_prob - six_prob - extras_prob
        remaining = max(0.15, remaining)
        
        one_prob = remaining * 0.55
        two_prob = remaining * 0.35
        three_prob = remaining * 0.10
        
        return {
            "dot": dot_prob,
            "one": one_prob,
            "two": two_prob,
            "three": three_prob,
            "four": four_prob,
            "six": six_prob,
            "wicket": wicket_prob,
            "extras": extras_prob
        }
    
    def sample_outcome(self, probabilities: Dict[str, float]) -> BallOutcome:
        """Sample an outcome based on probabilities"""
        r = random.random()
        cumulative = 0
        
        outcome_map = {
            "dot": BallOutcome.DOT,
            "one": BallOutcome.ONE,
            "two": BallOutcome.TWO,
            "three": BallOutcome.THREE,
            "four": BallOutcome.FOUR,
            "six": BallOutcome.SIX,
            "wicket": BallOutcome.WICKET,
            "extras": BallOutcome.WIDE
        }
        
        for outcome, prob in probabilities.items():
            cumulative += prob
            if r < cumulative:
                return outcome_map.get(outcome, BallOutcome.DOT)
        
        return BallOutcome.DOT
    
    def get_dismissal_type(self, bowler: Dict) -> str:
        """Get a realistic dismissal type based on bowler"""
        bowling_type = bowler.get("bowling_type", "pace").lower()
        
        if "spin" in bowling_type:
            options = [
                ("bowled", 0.25),
                ("lbw", 0.25),
                ("caught", 0.35),
                ("stumped", 0.15)
            ]
        else:
            options = [
                ("bowled", 0.25),
                ("lbw", 0.20),
                ("caught", 0.50),
                ("caught behind", 0.05)
            ]
        
        r = random.random()
        cumulative = 0
        for dismissal, prob in options:
            cumulative += prob
            if r < cumulative:
                return dismissal
        return "caught"
    
    # ==================== BOWLING SELECTION ====================
    
    def get_bowling_priority(self, player: Dict) -> float:
        """Calculate bowling priority score for a player"""
        bowling = player.get("bowling", {})
        role = player.get("role", "").lower()
        
        wickets_per_over = bowling.get("wickets_per_over", 0)
        economy = bowling.get("economy", 10)
        
        if "bowler" in role and "all" not in role:
            base_priority = 100
        elif "all" in role or "rounder" in role:
            base_priority = 60
        else:
            base_priority = 0
        
        if wickets_per_over > 0:
            effectiveness_bonus = (wickets_per_over * 100) + ((8 - min(economy, 8)) * 5)
            base_priority += effectiveness_bonus
        
        return base_priority
    
    def select_bowlers_for_innings(self, bowling_lineup: List[Dict]) -> List[Dict]:
        """Select and order bowlers by priority"""
        players_with_priority = []
        for player in bowling_lineup:
            priority = self.get_bowling_priority(player)
            players_with_priority.append((player, priority))
        
        players_with_priority.sort(key=lambda x: x[1], reverse=True)
        
        main_bowlers = [(p, pri) for p, pri in players_with_priority if pri >= 10]
        backup_bowlers = [(p, pri) for p, pri in players_with_priority if pri < 10]
        
        selected = []
        for player, priority in main_bowlers[:5]:
            selected.append(player)
        
        if len(selected) < 5:
            for player, priority in backup_bowlers[:5 - len(selected)]:
                selected.append(player)
        
        return selected
    
    def get_next_bowler(self, innings: InningsState, match_situation: Dict) -> int:
        """Select next bowler intelligently"""
        available = []
        
        for idx, bowler in enumerate(innings.bowlers):
            if bowler.overs >= 10:
                continue
            
            priority = self.get_bowling_priority(bowler.player)
            fatigue_penalty = bowler.fatigue * 20
            
            phase_bonus = 0
            if innings.phase == MatchPhase.POWERPLAY and priority > 80:
                phase_bonus = 30
            elif innings.phase == MatchPhase.DEATH and priority > 80:
                phase_bonus = 40
            
            effective_priority = priority - fatigue_penalty + phase_bonus
            
            if idx == innings.current_bowler_idx:
                effective_priority -= 200
            
            available.append((idx, effective_priority, bowler.overs))
        
        if not available:
            for idx, bowler in enumerate(innings.bowlers):
                if bowler.overs < 10 and idx != innings.current_bowler_idx:
                    return idx
            return (innings.current_bowler_idx + 1) % len(innings.bowlers)
        
        available.sort(key=lambda x: x[1], reverse=True)
        return available[0][0]
    
    # ==================== BALL SIMULATION ====================
    
    def simulate_ball(self, innings: InningsState, match_situation: Dict) -> Dict:
        """Simulate a single ball with all modifiers"""
        striker = innings.batters[innings.striker_idx]
        bowler = innings.bowlers[innings.current_bowler_idx]
        
        # Get actual batting position
        actual_position = innings.striker_idx + 1
        
        # Calculate probabilities
        probs = self.calculate_ball_probabilities(
            striker.player,
            striker,
            bowler.player,
            bowler,
            innings.phase,
            match_situation,
            innings,
            actual_position
        )
        
        # Sample outcome
        outcome = self.sample_outcome(probs)
        
        non_striker = innings.batters[innings.non_striker_idx]
        
        ball_data = {
            "ball_number": innings.balls + 1,
            "over": int(innings.overs) + 1,
            "ball_in_over": (innings.balls % 6) + 1,
            "batter": striker.player["name"],
            "non_striker": non_striker.player["name"],
            "bowler": bowler.player["name"],
            "outcome": None,
            "runs": 0,
            "is_wicket": False,
            "is_extra": False,
            "is_boundary": False,
            "total_after": innings.runs,
            "wickets_after": innings.wickets,
            "run_rate": round(innings.current_run_rate, 2) if innings.overs > 0 else 0,
            "required_rr": round(innings.required_run_rate, 2) if innings.required_run_rate else None
        }
        
        legal_ball = True
        
        if outcome == BallOutcome.WICKET:
            dismissal = self.get_dismissal_type(bowler.player)
            striker.is_out = True
            striker.dismissal_type = dismissal
            striker.dismissed_by = bowler.player["name"]
            striker.balls_faced += 1
            bowler.wickets += 1
            bowler.balls_bowled += 1
            bowler.spell_balls += 1
            bowler.dots_in_current_over += 1
            innings.wickets += 1
            innings.fall_of_wickets.append({
                "wicket": innings.wickets,
                "runs": innings.runs,
                "batter": striker.player["name"],
                "dismissal": dismissal,
                "bowler": bowler.player["name"],
                "overs": innings.overs
            })
            ball_data["outcome"] = f"OUT! {dismissal}"
            ball_data["is_wicket"] = True
            ball_data["dismissal_type"] = dismissal
            innings.momentum = max(-1, innings.momentum - 0.2)
            
        elif outcome in [BallOutcome.WIDE, BallOutcome.NO_BALL]:
            runs = 1
            innings.runs += runs
            innings.extras += runs
            bowler.runs_conceded += runs
            bowler.extras += runs
            bowler.current_over_runs += runs
            legal_ball = False
            ball_data["outcome"] = "wide" if outcome == BallOutcome.WIDE else "no ball"
            ball_data["runs"] = runs
            ball_data["is_extra"] = True
            
        else:
            runs = outcome.value
            innings.runs += runs
            striker.runs += runs
            striker.balls_faced += 1
            bowler.runs_conceded += runs
            bowler.balls_bowled += 1
            bowler.spell_balls += 1
            bowler.current_over_runs += runs
            
            if runs == 0:
                bowler.dots_in_current_over += 1
                ball_data["outcome"] = "."
                innings.momentum = max(-1, innings.momentum - 0.02)
            elif runs == 4:
                striker.fours += 1
                ball_data["outcome"] = "FOUR"
                ball_data["is_boundary"] = True
                innings.momentum = min(1, innings.momentum + 0.1)
            elif runs == 6:
                striker.sixes += 1
                ball_data["outcome"] = "SIX"
                ball_data["is_boundary"] = True
                innings.momentum = min(1, innings.momentum + 0.15)
            else:
                ball_data["outcome"] = str(runs)
                if runs >= 2:
                    innings.momentum = min(1, innings.momentum + 0.03)
            
            ball_data["runs"] = runs
            
            if runs % 2 == 1:
                innings.striker_idx, innings.non_striker_idx = innings.non_striker_idx, innings.striker_idx
        
        ball_data["total_after"] = innings.runs
        ball_data["wickets_after"] = innings.wickets
        
        if legal_ball:
            innings.balls += 1
            new_over_number = innings.balls // 6
            balls_in_over = innings.balls % 6
            innings.overs = new_over_number + (balls_in_over / 10)
            
            if balls_in_over == 0 and innings.balls > 0:
                if bowler.current_over_runs == 0:
                    bowler.maidens += 1
                
                bowler.fatigue = min(1.0, bowler.fatigue + 0.12)
                bowler.current_over_runs = 0
                bowler.dots_in_current_over = 0
                
                innings.striker_idx, innings.non_striker_idx = innings.non_striker_idx, innings.striker_idx
                
                bowler.overs = bowler.balls_bowled / 6
                innings.current_bowler_idx = self.get_next_bowler(innings, match_situation)
        
        innings.ball_log.append(ball_data)
        return ball_data
    
    # ==================== INNINGS SIMULATION ====================
    
    def simulate_innings(
        self,
        batting_team: str,
        bowling_team: str,
        batting_lineup: List[Dict],
        bowling_lineup: List[Dict],
        target: Optional[int] = None,
        max_overs: int = 50
    ) -> InningsState:
        """Simulate a complete innings"""
        
        innings = InningsState(
            batting_team=batting_team,
            bowling_team=bowling_team,
            batting_lineup=batting_lineup,
            bowling_lineup=bowling_lineup,
            target=target
        )
        
        # Calculate team fielding modifier (simplified)
        innings.team_fielding_modifier = self.calculate_team_fielding_modifier(bowling_lineup)
        
        # Initialize batters
        for player in batting_lineup[:2]:
            innings.batters.append(BatterState(player=player))
        
        # Select bowlers intelligently
        selected_bowlers = self.select_bowlers_for_innings(bowling_lineup)
        for player in selected_bowlers:
            innings.bowlers.append(BowlerState(player=player))
        
        next_batter_idx = 2
        
        while innings.balls < max_overs * 6 and innings.wickets < 10:
            if target is not None and innings.runs >= target:
                break
            
            match_situation = {
                "chasing": target is not None,
                "target": target,
                "required_run_rate": innings.required_run_rate,
                "current_run_rate": innings.current_run_rate,
                "wickets_down": innings.wickets,
                "overs_remaining": max_overs - int(innings.overs),
                "momentum": innings.momentum
            }
            
            ball_result = self.simulate_ball(innings, match_situation)
            
            if ball_result["is_wicket"] and innings.wickets < 10 and next_batter_idx < len(batting_lineup):
                new_batter = BatterState(player=batting_lineup[next_batter_idx])
                innings.batters.append(new_batter)
                innings.striker_idx = len(innings.batters) - 1
                next_batter_idx += 1
        
        for bowler in innings.bowlers:
            bowler.overs = bowler.balls_bowled / 6
        
        return innings
    
    # ==================== MATCH SIMULATION ====================
    
    def simulate_match(
        self,
        team1_name: str,
        team2_name: str,
        team1_lineup: List[Dict],
        team2_lineup: List[Dict],
        toss_winner: Optional[str] = None,
        toss_decision: Optional[str] = None
    ) -> Dict:
        """Simulate a complete ODI match"""
        
        if toss_winner is None:
            toss_winner = random.choice([team1_name, team2_name])
        if toss_decision is None:
            toss_decision = random.choice(["bat", "bowl"])
        
        if toss_winner == team1_name:
            if toss_decision == "bat":
                batting_first = (team1_name, team1_lineup)
                batting_second = (team2_name, team2_lineup)
            else:
                batting_first = (team2_name, team2_lineup)
                batting_second = (team1_name, team1_lineup)
        else:
            if toss_decision == "bat":
                batting_first = (team2_name, team2_lineup)
                batting_second = (team1_name, team1_lineup)
            else:
                batting_first = (team1_name, team1_lineup)
                batting_second = (team2_name, team2_lineup)
        
        first_innings = self.simulate_innings(
            batting_team=batting_first[0],
            bowling_team=batting_second[0],
            batting_lineup=batting_first[1],
            bowling_lineup=batting_second[1]
        )
        
        target = first_innings.runs + 1
        
        second_innings = self.simulate_innings(
            batting_team=batting_second[0],
            bowling_team=batting_first[0],
            batting_lineup=batting_second[1],
            bowling_lineup=batting_first[1],
            target=target
        )
        
        # Determine result
        if second_innings.runs >= target:
            winner = batting_second[0]
            margin = f"{10 - second_innings.wickets} wickets"
        else:
            winner = batting_first[0]
            margin = f"{target - second_innings.runs - 1} runs"
        
        return {
            "toss": {
                "winner": toss_winner,
                "decision": toss_decision
            },
            "first_innings": self.innings_to_dict(first_innings),
            "second_innings": self.innings_to_dict(second_innings),
            "result": {
                "winner": winner,
                "margin": margin
            }
        }
    
    def innings_to_dict(self, innings: InningsState) -> Dict:
        """Convert innings state to dictionary"""
        return {
            "batting_team": innings.batting_team,
            "bowling_team": innings.bowling_team,
            "runs": innings.runs,
            "wickets": innings.wickets,
            "overs": round(innings.overs, 1),
            "extras": innings.extras,
            "run_rate": round(innings.current_run_rate, 2),
            "batters": [
                {
                    "name": b.player["name"],
                    "runs": b.runs,
                    "balls": b.balls_faced,
                    "fours": b.fours,
                    "sixes": b.sixes,
                    "strike_rate": round(b.strike_rate, 2),
                    "is_out": b.is_out,
                    "dismissal": f"{b.dismissal_type}" if b.is_out else "not out",
                    "dismissed_by": b.dismissed_by
                }
                for b in innings.batters
            ],
            "bowlers": [
                {
                    "name": b.player["name"],
                    "overs": round(b.overs, 1),
                    "maidens": b.maidens,
                    "runs": b.runs_conceded,
                    "wickets": b.wickets,
                    "economy": round(b.economy, 2)
                }
                for b in innings.bowlers if b.balls_bowled > 0
            ],
            "fall_of_wickets": innings.fall_of_wickets,
            "ball_log": innings.ball_log
        }
