import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  SafeAreaView,
  StatusBar,
  FlatList,
  Modal,
  Alert,
  TextInput,
  Dimensions,
} from 'react-native';
import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;
const { width: SCREEN_WIDTH } = Dimensions.get('window');

// Types
interface Player {
  id: string;
  name: string;
  country: string;
  role: string;
  batting_style: string;
  bowling_style: string;
  batting: { average: number; strike_rate: number; powerplay_sr?: number };
  bowling: { economy: number; wickets_per_over: number };
  era: string;
}

interface BallData {
  ball_number: number;
  over: number;
  ball_in_over: number;
  batter: string;
  non_striker?: string;
  bowler: string;
  outcome: string;
  runs: number;
  is_wicket: boolean;
  is_boundary?: boolean;
  total_after: number;
  wickets_after: number;
}

interface BatterScore {
  name: string;
  runs: number;
  balls: number;
  fours: number;
  sixes: number;
  strike_rate: number;
  is_out: boolean;
  dismissal: string;
}

interface BowlerScore {
  name: string;
  overs: number;
  maidens: number;
  runs: number;
  wickets: number;
  economy: number;
}

interface Innings {
  batting_team: string;
  bowling_team: string;
  runs: number;
  wickets: number;
  overs: number;
  extras: number;
  run_rate: number;
  batters: BatterScore[];
  bowlers: BowlerScore[];
  ball_log: BallData[];
}

interface MatchResult {
  match_id?: string;
  toss: { winner: string; decision: string };
  first_innings: Innings;
  second_innings: Innings;
  result: { winner: string; margin: string };
  seed?: number;
}

interface MatchHistoryItem {
  id: string;
  team1_name: string;
  team2_name: string;
  team1_score: number;
  team2_score: number;
  team1_wickets: number;
  team2_wickets: number;
  winner: string;
  margin: string;
  created_at: string;
  first_innings: Innings;
  second_innings: Innings;
  toss: { winner: string; decision: string };
}

type Screen = 'home' | 'draftSetup' | 'draft' | 'battingOrder' | 'live' | 'scorecard' | 'history' | 'historyDetail';
type DraftMode = 'human' | 'ai';
type AIDifficulty = 'easy' | 'medium' | 'hard';
type SimSpeed = 1 | 2 | 4;

// Light Theme Colors
const COLORS = {
  background: '#F8F9FA',
  card: '#FFFFFF',
  primary: '#4A90A4',
  primaryLight: '#E8F4F8',
  accent: '#5B9A8B',
  text: '#2D3436',
  textSecondary: '#636E72',
  textLight: '#B2BEC3',
  border: '#E9ECEF',
  success: '#5B9A8B',
  danger: '#C0392B',
  warning: '#D4A574',
  boundary: '#4A90A4',
  wicket: '#C0392B',
  dot: '#B2BEC3',
};

export default function CricketSimulator() {
  // Navigation
  const [currentScreen, setCurrentScreen] = useState<Screen>('home');
  const [previousScreen, setPreviousScreen] = useState<Screen>('home');
  
  // Players
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(false);
  
  // Draft Setup
  const [draftMode, setDraftMode] = useState<DraftMode>('human');
  const [aiDifficulty, setAIDifficulty] = useState<AIDifficulty>('medium');
  
  // Teams
  const [team1, setTeam1] = useState<Player[]>([]);
  const [team2, setTeam2] = useState<Player[]>([]);
  const [team1Name, setTeam1Name] = useState('Your XI');
  const [team2Name, setTeam2Name] = useState('Opponent XI');
  const [team1Order, setTeam1Order] = useState<Player[]>([]);
  const [team2Order, setTeam2Order] = useState<Player[]>([]);
  const [currentOrderTeam, setCurrentOrderTeam] = useState<1 | 2>(1);
  
  // AI Draft turn-by-turn
  const [aiPicks, setAIPicks] = useState<Player[]>([]);
  const [isAIThinking, setIsAIThinking] = useState(false);
  const [aiLastReasoning, setAILastReasoning] = useState('');
  
  // Match
  const [matchResult, setMatchResult] = useState<MatchResult | null>(null);
  const [selectedInnings, setSelectedInnings] = useState<1 | 2>(1);
  
  // Draft Modal
  const [showPlayerModal, setShowPlayerModal] = useState(false);
  const [currentTeam, setCurrentTeam] = useState<1 | 2>(1);
  const [countryFilter, setCountryFilter] = useState<string | null>(null);
  const [roleFilter, setRoleFilter] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  
  // Live simulation
  const [liveMode, setLiveMode] = useState(false);
  const [liveInnings, setLiveInnings] = useState<1 | 2>(1);
  const [liveBallIndex, setLiveBallIndex] = useState(0);
  const [simSpeed, setSimSpeed] = useState<SimSpeed>(2);
  const [isPaused, setIsPaused] = useState(false);
  const liveIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const commentaryScrollRef = useRef<ScrollView>(null);
  
  // History
  const [matchHistory, setMatchHistory] = useState<MatchHistoryItem[]>([]);
  const [selectedHistoryMatch, setSelectedHistoryMatch] = useState<MatchHistoryItem | null>(null);

  useEffect(() => {
    fetchPlayers();
  }, []);

  // Live simulation effect
  useEffect(() => {
    if (liveMode && matchResult && !isPaused) {
      const innings = liveInnings === 1 ? matchResult.first_innings : matchResult.second_innings;
      const ballLog = innings.ball_log;
      
      if (liveBallIndex < ballLog.length) {
        const delay = 2000 / simSpeed;
        liveIntervalRef.current = setTimeout(() => {
          setLiveBallIndex(prev => prev + 1);
          setTimeout(() => {
            commentaryScrollRef.current?.scrollToEnd({ animated: true });
          }, 100);
        }, delay / 6);
      } else if (liveInnings === 1) {
        setLiveInnings(2);
        setLiveBallIndex(0);
      } else {
        setLiveMode(false);
        navigateTo('scorecard');
      }
    }
    
    return () => {
      if (liveIntervalRef.current) clearTimeout(liveIntervalRef.current);
    };
  }, [liveMode, liveBallIndex, liveInnings, simSpeed, isPaused, matchResult]);

  const navigateTo = (screen: Screen) => {
    setPreviousScreen(currentScreen);
    setCurrentScreen(screen);
  };

  const goBack = () => {
    if (currentScreen === 'draft') {
      navigateTo('draftSetup');
    } else if (currentScreen === 'battingOrder') {
      navigateTo('draft');
    } else if (currentScreen === 'draftSetup') {
      navigateTo('home');
    } else if (currentScreen === 'scorecard' || currentScreen === 'live') {
      navigateTo('home');
    } else if (currentScreen === 'historyDetail') {
      navigateTo('history');
    } else if (currentScreen === 'history') {
      navigateTo('home');
    } else {
      navigateTo('home');
    }
  };

  const fetchPlayers = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${BACKEND_URL}/api/players`);
      const data = await response.json();
      setPlayers(data);
    } catch (error) {
      console.error('Error fetching players:', error);
      Alert.alert('Error', 'Failed to load players');
    } finally {
      setLoading(false);
    }
  };

  const fetchMatchHistory = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${BACKEND_URL}/api/matches/history`);
      const data = await response.json();
      setMatchHistory(data);
    } catch (error) {
      console.error('Error fetching history:', error);
    } finally {
      setLoading(false);
    }
  };

  const addPlayerToTeam = async (player: Player) => {
    if (currentTeam === 1) {
      if (team1.length >= 11) return;
      if (team1.find(p => p.id === player.id)) return;
      setTeam1([...team1, player]);
      setShowPlayerModal(false);
      
      // In AI mode, trigger AI pick after user picks
      if (draftMode === 'ai' && team1.length < 11 && aiPicks.length < 11) {
        // Small delay to show user's pick first
        setTimeout(() => makeAIPick(), 500);
      }
    } else {
      if (team2.length >= 11) return;
      if (team2.find(p => p.id === player.id)) return;
      setTeam2([...team2, player]);
      setShowPlayerModal(false);
    }
  };

  const removePlayerFromTeam = (playerId: string, teamNum: 1 | 2) => {
    if (teamNum === 1) {
      setTeam1(team1.filter(p => p.id !== playerId));
    } else {
      setTeam2(team2.filter(p => p.id !== playerId));
    }
  };

  const generateAITeam = async () => {
    if (team1.length !== 11) {
      Alert.alert('Incomplete Team', 'Please draft your team first (11 players)');
      return;
    }
    
    try {
      setLoading(true);
      const response = await fetch(`${BACKEND_URL}/api/draft/ai-team`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_team: team1.map(p => p.id),
          difficulty: aiDifficulty
        }),
      });
      const data = await response.json();
      
      if (data.players) {
        const aiPlayers = data.players.filter((p: Player | null) => p !== null) as Player[];
        setTeam2(aiPlayers);
        setAIPicks(aiPlayers);
        setTeam2Name(`AI ${aiDifficulty.charAt(0).toUpperCase() + aiDifficulty.slice(1)}`);
      } else {
        Alert.alert('Error', 'Failed to generate AI team');
      }
    } catch (error) {
      console.error('Error generating AI team:', error);
      Alert.alert('Error', 'Failed to generate AI team');
    } finally {
      setLoading(false);
    }
  };

  // Turn-by-turn AI pick after user picks
  const makeAIPick = async () => {
    if (aiPicks.length >= 11) return;
    
    try {
      setIsAIThinking(true);
      const response = await fetch(`${BACKEND_URL}/api/draft/ai-single-pick`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_picks: team1.map(p => p.id),
          ai_picks: aiPicks.map(p => p.id),
          difficulty: aiDifficulty
        }),
      });
      const data = await response.json();
      
      if (data.player) {
        setAIPicks(prev => [...prev, data.player]);
        setTeam2(prev => [...prev, data.player]);
        setAILastReasoning(data.reasoning || '');
      }
    } catch (error) {
      console.error('Error getting AI pick:', error);
    } finally {
      setIsAIThinking(false);
    }
  };

  const autoPickTeam = (teamNum: 1 | 2) => {
    const otherTeam = teamNum === 1 ? team2 : team1;
    const pickedIds = new Set(otherTeam.map(p => p.id));
    
    const available = players.filter(p => !pickedIds.has(p.id));
    const shuffled = [...available].sort(() => Math.random() - 0.5);
    
    const batters = shuffled.filter(p => p.role.includes('Batsman') || p.role.includes('Wicketkeeper'));
    const allrounders = shuffled.filter(p => p.role.includes('All-rounder'));
    const bowlers = shuffled.filter(p => p.role === 'Bowler');
    
    const newTeam = [...batters.slice(0, 5), ...allrounders.slice(0, 2), ...bowlers.slice(0, 4)];
    
    if (teamNum === 1) {
      setTeam1(newTeam);
    } else {
      setTeam2(newTeam);
    }
  };

  const getDefaultBattingOrder = (team: Player[]): Player[] => {
    const openers: Player[] = [];
    const topOrder: Player[] = [];
    const middle: Player[] = [];
    const lower: Player[] = [];
    const tail: Player[] = [];
    
    team.forEach(p => {
      const role = p.role;
      const avg = p.batting?.average || 20;
      const ppSr = p.batting?.powerplay_sr || 70;
      
      if ((role.includes('Wicketkeeper') || role.includes('Batsman')) && ppSr > 85) {
        openers.push(p);
      } else if ((role.includes('Batsman') || role.includes('Wicketkeeper')) && avg > 35) {
        topOrder.push(p);
      } else if (role.includes('All-rounder') && avg > 25) {
        middle.push(p);
      } else if (role.includes('All-rounder')) {
        lower.push(p);
      } else if (role === 'Bowler') {
        tail.push(p);
      } else {
        middle.push(p);
      }
    });
    
    openers.sort((a, b) => (b.batting?.powerplay_sr || 0) - (a.batting?.powerplay_sr || 0));
    topOrder.sort((a, b) => (b.batting?.average || 0) - (a.batting?.average || 0));
    middle.sort((a, b) => (b.batting?.average || 0) - (a.batting?.average || 0));
    tail.sort((a, b) => (b.batting?.average || 0) - (a.batting?.average || 0));
    
    const order = [...openers.slice(0, 2), ...topOrder.slice(0, 3), ...middle, ...lower, ...tail];
    const remaining = team.filter(p => !order.includes(p));
    
    return [...order, ...remaining].slice(0, 11);
  };

  const proceedToBattingOrder = () => {
    if (team1.length !== 11 || team2.length !== 11) {
      Alert.alert('Incomplete Teams', 'Both teams need 11 players');
      return;
    }
    
    setTeam1Order(getDefaultBattingOrder(team1));
    setTeam2Order(getDefaultBattingOrder(team2));
    setCurrentOrderTeam(1);
    navigateTo('battingOrder');
  };

  const moveBatterUp = (index: number) => {
    if (index === 0) return;
    const order = currentOrderTeam === 1 ? [...team1Order] : [...team2Order];
    [order[index - 1], order[index]] = [order[index], order[index - 1]];
    if (currentOrderTeam === 1) setTeam1Order(order);
    else setTeam2Order(order);
  };

  const moveBatterDown = (index: number) => {
    const order = currentOrderTeam === 1 ? team1Order : team2Order;
    if (index === order.length - 1) return;
    const newOrder = [...order];
    [newOrder[index], newOrder[index + 1]] = [newOrder[index + 1], newOrder[index]];
    if (currentOrderTeam === 1) setTeam1Order(newOrder);
    else setTeam2Order(newOrder);
  };

  const runSimulation = async (goLive: boolean = false) => {
    try {
      setLoading(true);
      
      const response = await fetch(`${BACKEND_URL}/api/matches/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          team1: { team_name: team1Name, player_ids: team1Order.map(p => p.id) },
          team2: { team_name: team2Name, player_ids: team2Order.map(p => p.id) },
          simulation_mode: goLive ? 'live' : 'quick',
        }),
      });
      const data = await response.json();
      setMatchResult(data.result);
      
      if (goLive) {
        setLiveMode(true);
        setLiveInnings(1);
        setLiveBallIndex(0);
        setIsPaused(false);
        navigateTo('live');
      } else {
        navigateTo('scorecard');
      }
    } catch (error) {
      console.error('Error running simulation:', error);
      Alert.alert('Error', 'Failed to run simulation');
    } finally {
      setLoading(false);
    }
  };

  const runQuickSimulation = async (goLive: boolean = false) => {
    try {
      setLoading(true);
      const response = await fetch(`${BACKEND_URL}/api/matches/quick-sim`, { method: 'POST' });
      const data = await response.json();
      setMatchResult(data);
      
      if (goLive) {
        setLiveMode(true);
        setLiveInnings(1);
        setLiveBallIndex(0);
        setIsPaused(false);
        navigateTo('live');
      } else {
        navigateTo('scorecard');
      }
    } catch (error) {
      console.error('Error:', error);
      Alert.alert('Error', 'Failed to run simulation');
    } finally {
      setLoading(false);
    }
  };

  const viewHistoryMatch = (match: MatchHistoryItem) => {
    setSelectedHistoryMatch(match);
    setMatchResult({
      match_id: match.id,
      toss: match.toss || { winner: match.team1_name, decision: 'bat' },
      first_innings: match.first_innings,
      second_innings: match.second_innings,
      result: { winner: match.winner, margin: match.margin }
    });
    setSelectedInnings(1);
    navigateTo('historyDetail');
  };

  const replayHistoryMatch = (match: MatchHistoryItem) => {
    setSelectedHistoryMatch(match);
    setMatchResult({
      match_id: match.id,
      toss: match.toss || { winner: match.team1_name, decision: 'bat' },
      first_innings: match.first_innings,
      second_innings: match.second_innings,
      result: { winner: match.winner, margin: match.margin }
    });
    setLiveMode(true);
    setLiveInnings(1);
    setLiveBallIndex(0);
    setIsPaused(false);
    navigateTo('live');
  };

  const resetDraft = () => {
    setTeam1([]);
    setTeam2([]);
    setTeam1Order([]);
    setTeam2Order([]);
    setAIPicks([]);
    setAILastReasoning('');
    setTeam1Name('Your XI');
    setTeam2Name('Opponent XI');
  };

  const clearMatchHistory = async () => {
    Alert.alert(
      'Clear History',
      'Are you sure you want to delete all match history?',
      [
        { text: 'Cancel', style: 'cancel' },
        { 
          text: 'Clear All', 
          style: 'destructive',
          onPress: async () => {
            try {
              await fetch(`${BACKEND_URL}/api/matches/history`, { method: 'DELETE' });
              setMatchHistory([]);
            } catch (error) {
              console.error('Error clearing history:', error);
            }
          }
        }
      ]
    );
  };

  const filteredPlayers = players.filter(p => {
    if (searchQuery && !p.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    if (countryFilter && p.country !== countryFilter) return false;
    if (roleFilter && !p.role.includes(roleFilter)) return false;
    return true;
  });

  const countries = [...new Set(players.map(p => p.country))].sort();
  const roles = ['Batsman', 'Bowler', 'All-rounder', 'Wicketkeeper'];

  const highlightText = (text: string, query: string) => {
    if (!query) return <Text style={styles.playerName}>{text}</Text>;
    const parts = text.split(new RegExp(`(${query})`, 'gi'));
    return (
      <Text style={styles.playerName}>
        {parts.map((part, i) => 
          part.toLowerCase() === query.toLowerCase() 
            ? <Text key={i} style={styles.highlightedText}>{part}</Text>
            : part
        )}
      </Text>
    );
  };

  const getBallColor = (ball: BallData) => {
    if (ball.is_wicket) return COLORS.wicket;
    if (ball.is_boundary) return COLORS.boundary;
    if (ball.runs === 0 && !ball.outcome?.includes('wide')) return COLORS.dot;
    return COLORS.text;
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  // ============ SCREENS ============

  // Home Screen
  const renderHomeScreen = () => (
    <ScrollView style={styles.screenContainer} contentContainerStyle={styles.screenContent}>
      <View style={styles.heroSection}>
        <MaterialCommunityIcons name="cricket" size={72} color={COLORS.primary} />
        <Text style={styles.heroTitle}>Cricket Simulator</Text>
        <Text style={styles.heroSubtitle}>ODI Match Engine</Text>
      </View>

      <View style={styles.actionButtons}>
        <TouchableOpacity style={styles.primaryButton} onPress={() => { resetDraft(); navigateTo('draftSetup'); }}>
          <Ionicons name="people-outline" size={22} color="#fff" />
          <Text style={styles.primaryButtonText}>Draft Teams</Text>
        </TouchableOpacity>

        <View style={styles.buttonRow}>
          <TouchableOpacity style={styles.secondaryButtonHalf} onPress={() => runQuickSimulation(false)} disabled={loading}>
            <Ionicons name="flash-outline" size={20} color={COLORS.primary} />
            <Text style={styles.secondaryButtonText}>Quick Sim</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.secondaryButtonHalf} onPress={() => runQuickSimulation(true)} disabled={loading}>
            <Ionicons name="play-circle-outline" size={20} color={COLORS.primary} />
            <Text style={styles.secondaryButtonText}>Live Match</Text>
          </TouchableOpacity>
        </View>

        <TouchableOpacity style={styles.outlineButton} onPress={() => { fetchMatchHistory(); navigateTo('history'); }}>
          <Ionicons name="time-outline" size={20} color={COLORS.primary} />
          <Text style={styles.outlineButtonText}>Match History</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.statsCard}>
        <Text style={styles.statsTitle}>Available Players</Text>
        <View style={styles.statsRow}>
          <View style={styles.statItem}>
            <Text style={styles.statNumber}>{players.length}</Text>
            <Text style={styles.statLabel}>Players</Text>
          </View>
          <View style={styles.statItem}>
            <Text style={styles.statNumber}>{countries.length}</Text>
            <Text style={styles.statLabel}>Countries</Text>
          </View>
          <View style={styles.statItem}>
            <Text style={styles.statNumber}>50</Text>
            <Text style={styles.statLabel}>Overs</Text>
          </View>
        </View>
      </View>
    </ScrollView>
  );

  // Draft Setup Screen
  const renderDraftSetupScreen = () => (
    <View style={styles.screenContainer}>
      <View style={styles.header}>
        <TouchableOpacity onPress={goBack} style={styles.headerButton}>
          <Ionicons name="arrow-back" size={24} color={COLORS.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Draft Setup</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView style={styles.setupContainer}>
        <Text style={styles.setupSectionTitle}>Draft Mode</Text>
        <View style={styles.optionCards}>
          <TouchableOpacity
            style={[styles.optionCard, draftMode === 'human' && styles.optionCardActive]}
            onPress={() => setDraftMode('human')}
          >
            <Ionicons name="people" size={32} color={draftMode === 'human' ? COLORS.primary : COLORS.textSecondary} />
            <Text style={[styles.optionCardTitle, draftMode === 'human' && styles.optionCardTitleActive]}>vs Human</Text>
            <Text style={styles.optionCardDesc}>Draft both teams manually</Text>
          </TouchableOpacity>
          
          <TouchableOpacity
            style={[styles.optionCard, draftMode === 'ai' && styles.optionCardActive]}
            onPress={() => setDraftMode('ai')}
          >
            <Ionicons name="hardware-chip" size={32} color={draftMode === 'ai' ? COLORS.primary : COLORS.textSecondary} />
            <Text style={[styles.optionCardTitle, draftMode === 'ai' && styles.optionCardTitleActive]}>vs AI</Text>
            <Text style={styles.optionCardDesc}>AI drafts opponent team</Text>
          </TouchableOpacity>
        </View>

        {draftMode === 'ai' && (
          <>
            <Text style={styles.setupSectionTitle}>AI Difficulty</Text>
            <View style={styles.difficultyOptions}>
              {(['easy', 'medium', 'hard'] as AIDifficulty[]).map(diff => (
                <TouchableOpacity
                  key={diff}
                  style={[styles.difficultyChip, aiDifficulty === diff && styles.difficultyChipActive]}
                  onPress={() => setAIDifficulty(diff)}
                >
                  <Text style={[styles.difficultyChipText, aiDifficulty === diff && styles.difficultyChipTextActive]}>
                    {diff.charAt(0).toUpperCase() + diff.slice(1)}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            <View style={styles.difficultyInfo}>
              {aiDifficulty === 'easy' && <Text style={styles.difficultyInfoText}>AI makes suboptimal picks, reactive drafting</Text>}
              {aiDifficulty === 'medium' && <Text style={styles.difficultyInfoText}>AI uses balanced drafting strategy</Text>}
              {aiDifficulty === 'hard' && <Text style={styles.difficultyInfoText}>AI counter-drafts and optimizes for win probability</Text>}
            </View>
          </>
        )}

        <Text style={styles.setupSectionTitle}>Team Names</Text>
        <View style={styles.teamNameInputs}>
          <View style={styles.teamNameRow}>
            <Text style={styles.teamNameLabel}>Your Team:</Text>
            <TextInput
              style={styles.teamNameInput}
              value={team1Name}
              onChangeText={setTeam1Name}
              placeholder="Your XI"
              placeholderTextColor={COLORS.textLight}
              maxLength={20}
            />
          </View>
          {draftMode === 'human' && (
            <View style={styles.teamNameRow}>
              <Text style={styles.teamNameLabel}>Opponent:</Text>
              <TextInput
                style={styles.teamNameInput}
                value={team2Name}
                onChangeText={setTeam2Name}
                placeholder="Opponent XI"
                placeholderTextColor={COLORS.textLight}
                maxLength={20}
              />
            </View>
          )}
        </View>

        <TouchableOpacity style={styles.startDraftButton} onPress={() => navigateTo('draft')}>
          <Text style={styles.startDraftButtonText}>Start Draft</Text>
          <Ionicons name="arrow-forward" size={20} color="#fff" />
        </TouchableOpacity>
      </ScrollView>
    </View>
  );

  // Draft Screen
  const renderDraftScreen = () => (
    <View style={styles.screenContainer}>
      <View style={styles.header}>
        <TouchableOpacity onPress={goBack} style={styles.headerButton}>
          <Ionicons name="arrow-back" size={24} color={COLORS.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Draft Teams</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView style={styles.draftContainer}>
        {/* Team 1 */}
        <View style={styles.teamCard}>
          <View style={styles.teamHeader}>
            <Text style={styles.teamName}>{team1Name}</Text>
            <View style={styles.teamHeaderRight}>
              <Text style={styles.teamCount}>{team1.length}/11</Text>
              <TouchableOpacity onPress={() => autoPickTeam(1)} style={styles.autoPickBtn}>
                <Ionicons name="shuffle-outline" size={18} color={COLORS.primary} />
              </TouchableOpacity>
            </View>
          </View>
          <View style={styles.playerChips}>
            {team1.map(player => (
              <TouchableOpacity key={player.id} style={styles.playerChip} onPress={() => removePlayerFromTeam(player.id, 1)}>
                <Text style={styles.playerChipText}>{player.name}</Text>
                <Ionicons name="close" size={14} color={COLORS.danger} />
              </TouchableOpacity>
            ))}
            {team1.length < 11 && (
              <TouchableOpacity style={styles.addPlayerChip} onPress={() => { setCurrentTeam(1); setShowPlayerModal(true); }}>
                <Ionicons name="add" size={18} color={COLORS.primary} />
                <Text style={styles.addPlayerText}>Add</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>

        {/* Team 2 */}
        <View style={styles.teamCard}>
          <View style={styles.teamHeader}>
            <Text style={styles.teamName}>{draftMode === 'ai' ? `AI (${aiDifficulty})` : team2Name}</Text>
            <View style={styles.teamHeaderRight}>
              <Text style={styles.teamCount}>{team2.length}/11</Text>
              {draftMode === 'human' && (
                <TouchableOpacity onPress={() => autoPickTeam(2)} style={styles.autoPickBtn}>
                  <Ionicons name="shuffle-outline" size={18} color={COLORS.primary} />
                </TouchableOpacity>
              )}
            </View>
          </View>
          
          {draftMode === 'ai' ? (
            <View style={styles.aiTeamSection}>
              {/* Turn-by-turn AI picks */}
              {team2.length > 0 && (
                <View style={styles.playerChips}>
                  {team2.map(player => (
                    <View key={player.id} style={styles.playerChipReadonly}>
                      <Text style={styles.playerChipText}>{player.name}</Text>
                    </View>
                  ))}
                </View>
              )}
              
              {/* AI thinking indicator */}
              {isAIThinking && (
                <View style={styles.aiThinkingBox}>
                  <ActivityIndicator size="small" color={COLORS.primary} />
                  <Text style={styles.aiThinkingText}>AI is drafting...</Text>
                </View>
              )}
              
              {/* AI reasoning */}
              {aiLastReasoning && !isAIThinking && team2.length > 0 && (
                <View style={styles.aiReasoningBox}>
                  <Text style={styles.aiReasoningText}>{aiLastReasoning}</Text>
                </View>
              )}
              
              {/* Fallback: Generate full AI team button */}
              {team2.length === 0 && team1.length === 0 && (
                <Text style={styles.aiHintText}>Start drafting your team - AI will respond to each pick!</Text>
              )}
              
              {/* Option to generate all at once if user hasn't started */}
              {team1.length === 11 && team2.length === 0 && (
                <TouchableOpacity 
                  style={styles.generateAIButton} 
                  onPress={generateAITeam}
                  disabled={loading}
                >
                  {loading ? (
                    <ActivityIndicator color="#fff" size="small" />
                  ) : (
                    <>
                      <Ionicons name="hardware-chip-outline" size={20} color="#fff" />
                      <Text style={styles.generateAIButtonText}>Generate AI Team</Text>
                    </>
                  )}
                </TouchableOpacity>
              )}
            </View>
          ) : (
            <View style={styles.playerChips}>
              {team2.map(player => (
                <TouchableOpacity key={player.id} style={styles.playerChip} onPress={() => removePlayerFromTeam(player.id, 2)}>
                  <Text style={styles.playerChipText}>{player.name}</Text>
                  <Ionicons name="close" size={14} color={COLORS.danger} />
                </TouchableOpacity>
              ))}
              {team2.length < 11 && (
                <TouchableOpacity style={styles.addPlayerChip} onPress={() => { setCurrentTeam(2); setShowPlayerModal(true); }}>
                  <Ionicons name="add" size={18} color={COLORS.primary} />
                  <Text style={styles.addPlayerText}>Add</Text>
                </TouchableOpacity>
              )}
            </View>
          )}
        </View>

        <TouchableOpacity
          style={[styles.proceedButton, (team1.length !== 11 || team2.length !== 11) && styles.disabledButton]}
          onPress={proceedToBattingOrder}
          disabled={team1.length !== 11 || team2.length !== 11}
        >
          <Text style={styles.proceedButtonText}>Set Batting Order</Text>
          <Ionicons name="arrow-forward" size={20} color="#fff" />
        </TouchableOpacity>
      </ScrollView>

      {/* Player Selection Modal */}
      <Modal visible={showPlayerModal} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Select Player</Text>
              <TouchableOpacity onPress={() => setShowPlayerModal(false)} style={styles.modalCloseBtn}>
                <Ionicons name="close" size={24} color={COLORS.text} />
              </TouchableOpacity>
            </View>

            <View style={styles.searchContainer}>
              <Ionicons name="search" size={20} color={COLORS.textSecondary} />
              <TextInput
                style={styles.searchInput}
                placeholder="Search players..."
                placeholderTextColor={COLORS.textLight}
                value={searchQuery}
                onChangeText={setSearchQuery}
              />
              {searchQuery.length > 0 && (
                <TouchableOpacity onPress={() => setSearchQuery('')}>
                  <Ionicons name="close-circle" size={20} color={COLORS.textSecondary} />
                </TouchableOpacity>
              )}
            </View>

            <TouchableOpacity style={styles.filterToggle} onPress={() => setShowFilters(!showFilters)}>
              <Text style={styles.filterToggleText}>
                Filters {countryFilter || roleFilter ? `(${[countryFilter, roleFilter].filter(Boolean).join(', ')})` : ''}
              </Text>
              <Ionicons name={showFilters ? "chevron-up" : "chevron-down"} size={20} color={COLORS.textSecondary} />
            </TouchableOpacity>

            {showFilters && (
              <View style={styles.filtersContainer}>
                <Text style={styles.filterLabel}>Country</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterScroll}>
                  <TouchableOpacity style={[styles.filterChip, !countryFilter && styles.filterChipActive]} onPress={() => setCountryFilter(null)}>
                    <Text style={[styles.filterChipText, !countryFilter && styles.filterChipTextActive]}>All</Text>
                  </TouchableOpacity>
                  {countries.map(country => (
                    <TouchableOpacity key={country} style={[styles.filterChip, countryFilter === country && styles.filterChipActive]} onPress={() => setCountryFilter(country)}>
                      <Text style={[styles.filterChipText, countryFilter === country && styles.filterChipTextActive]}>{country}</Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
                <Text style={styles.filterLabel}>Role</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterScroll}>
                  <TouchableOpacity style={[styles.filterChip, !roleFilter && styles.filterChipActive]} onPress={() => setRoleFilter(null)}>
                    <Text style={[styles.filterChipText, !roleFilter && styles.filterChipTextActive]}>All</Text>
                  </TouchableOpacity>
                  {roles.map(role => (
                    <TouchableOpacity key={role} style={[styles.filterChip, roleFilter === role && styles.filterChipActive]} onPress={() => setRoleFilter(role)}>
                      <Text style={[styles.filterChipText, roleFilter === role && styles.filterChipTextActive]}>{role}</Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
              </View>
            )}

            <Text style={styles.resultCount}>{filteredPlayers.length} players found</Text>

            <FlatList
              data={filteredPlayers}
              keyExtractor={item => item.id}
              renderItem={({ item }) => {
                const isSelected = currentTeam === 1 ? team1.find(p => p.id === item.id) : team2.find(p => p.id === item.id);
                const isInOtherTeam = currentTeam === 1 ? team2.find(p => p.id === item.id) : team1.find(p => p.id === item.id);
                return (
                  <TouchableOpacity
                    style={[styles.playerListItem, isSelected && styles.playerListItemSelected, isInOtherTeam && styles.playerListItemDisabled]}
                    onPress={() => !isSelected && !isInOtherTeam && addPlayerToTeam(item)}
                    disabled={!!isSelected || !!isInOtherTeam}
                  >
                    <View style={styles.playerInfo}>
                      {highlightText(item.name, searchQuery)}
                      <Text style={styles.playerMeta}>{item.country} • {item.role}</Text>
                    </View>
                    <View style={styles.playerStats}>
                      <Text style={styles.playerStat}>Avg: {item.batting.average.toFixed(1)}</Text>
                      <Text style={styles.playerStat}>SR: {item.batting.strike_rate.toFixed(1)}</Text>
                    </View>
                    {isSelected && <Ionicons name="checkmark-circle" size={22} color={COLORS.success} />}
                    {isInOtherTeam && <Ionicons name="close-circle" size={22} color={COLORS.danger} />}
                  </TouchableOpacity>
                );
              }}
              style={styles.playerList}
            />
          </View>
        </View>
      </Modal>
    </View>
  );

  // Batting Order Screen
  const renderBattingOrderScreen = () => {
    const currentOrder = currentOrderTeam === 1 ? team1Order : team2Order;
    const teamName = currentOrderTeam === 1 ? team1Name : team2Name;

    return (
      <View style={styles.screenContainer}>
        <View style={styles.header}>
          <TouchableOpacity onPress={goBack} style={styles.headerButton}>
            <Ionicons name="arrow-back" size={24} color={COLORS.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Batting Order</Text>
          <View style={{ width: 40 }} />
        </View>

        <View style={styles.orderToggle}>
          <TouchableOpacity
            style={[styles.orderTab, currentOrderTeam === 1 && styles.orderTabActive]}
            onPress={() => setCurrentOrderTeam(1)}
          >
            <Text style={[styles.orderTabText, currentOrderTeam === 1 && styles.orderTabTextActive]}>{team1Name}</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.orderTab, currentOrderTeam === 2 && styles.orderTabActive]}
            onPress={() => setCurrentOrderTeam(2)}
          >
            <Text style={[styles.orderTabText, currentOrderTeam === 2 && styles.orderTabTextActive]}>{team2Name}</Text>
          </TouchableOpacity>
        </View>

        <ScrollView style={styles.orderContainer}>
          <Text style={styles.orderHint}>Drag players to reorder batting positions</Text>
          
          {currentOrder.map((player, index) => (
            <View key={player.id} style={styles.orderItem}>
              <View style={styles.orderPosition}>
                <Text style={styles.orderPositionText}>{index + 1}</Text>
              </View>
              <View style={styles.orderPlayerInfo}>
                <Text style={styles.orderPlayerName}>{player.name}</Text>
                <Text style={styles.orderPlayerRole}>{player.role}</Text>
              </View>
              <View style={styles.orderControls}>
                <TouchableOpacity onPress={() => moveBatterUp(index)} disabled={index === 0} style={[styles.orderBtn, index === 0 && styles.orderBtnDisabled]}>
                  <Ionicons name="chevron-up" size={20} color={index === 0 ? COLORS.textLight : COLORS.text} />
                </TouchableOpacity>
                <TouchableOpacity onPress={() => moveBatterDown(index)} disabled={index === 10} style={[styles.orderBtn, index === 10 && styles.orderBtnDisabled]}>
                  <Ionicons name="chevron-down" size={20} color={index === 10 ? COLORS.textLight : COLORS.text} />
                </TouchableOpacity>
              </View>
            </View>
          ))}
        </ScrollView>

        <View style={styles.orderActions}>
          <TouchableOpacity style={styles.simButtonOutline} onPress={() => runSimulation(true)}>
            <Ionicons name="play-circle-outline" size={20} color={COLORS.primary} />
            <Text style={styles.simButtonOutlineText}>Live Match</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.simButton} onPress={() => runSimulation(false)}>
            <Ionicons name="flash-outline" size={20} color="#fff" />
            <Text style={styles.simButtonText}>Quick Sim</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  // Live Screen
  const renderLiveScreen = () => {
    if (!matchResult) return null;
    const innings = liveInnings === 1 ? matchResult.first_innings : matchResult.second_innings;
    const ballLog = innings.ball_log;
    const currentBalls = ballLog.slice(0, liveBallIndex);
    const lastBall = currentBalls[currentBalls.length - 1];
    const currentRuns = lastBall?.total_after || 0;
    const currentWickets = lastBall?.wickets_after || 0;
    const currentOver = lastBall ? `${Math.floor((lastBall.ball_number - 1) / 6)}.${(lastBall.ball_number - 1) % 6}` : '0.0';

    return (
      <View style={styles.screenContainer}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => { setLiveMode(false); goBack(); }} style={styles.headerButton}>
            <Ionicons name="close" size={24} color={COLORS.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>{liveInnings === 1 ? '1st' : '2nd'} Innings</Text>
          <TouchableOpacity onPress={() => { setLiveMode(false); navigateTo('scorecard'); }} style={styles.headerButton}>
            <Text style={styles.skipText}>Skip</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.liveScoreContainer}>
          <Text style={styles.liveTeamName}>{innings.batting_team}</Text>
          <View style={styles.liveScoreRow}>
            <Text style={styles.liveScore}>{currentRuns}/{currentWickets}</Text>
            <Text style={styles.liveOvers}>({currentOver} ov)</Text>
          </View>
          {liveInnings === 2 && (
            <Text style={styles.liveTarget}>
              Need: {matchResult.first_innings.runs + 1 - currentRuns} from {Math.max(0, 300 - liveBallIndex)} balls
            </Text>
          )}
        </View>

        <View style={styles.currentPlayersCard}>
          <View style={styles.currentPlayerRow}>
            <View style={styles.currentPlayer}>
              <Text style={styles.currentPlayerLabel}>Striker</Text>
              <Text style={styles.currentPlayerName}>{lastBall?.batter || '—'}</Text>
            </View>
            <View style={styles.currentPlayer}>
              <Text style={styles.currentPlayerLabel}>Non-Striker</Text>
              <Text style={styles.currentPlayerName}>{lastBall?.non_striker || '—'}</Text>
            </View>
          </View>
          <View style={styles.bowlerRow}>
            <Text style={styles.currentPlayerLabel}>Bowler</Text>
            <Text style={styles.currentPlayerName}>{lastBall?.bowler || '—'}</Text>
          </View>
        </View>

        <View style={styles.speedControls}>
          {([1, 2, 4] as SimSpeed[]).map(speed => (
            <TouchableOpacity key={speed} style={[styles.speedButton, simSpeed === speed && styles.speedButtonActive]} onPress={() => setSimSpeed(speed)}>
              <Text style={[styles.speedButtonText, simSpeed === speed && styles.speedButtonTextActive]}>{speed}×</Text>
            </TouchableOpacity>
          ))}
          <TouchableOpacity style={styles.pauseButton} onPress={() => setIsPaused(!isPaused)}>
            <Ionicons name={isPaused ? "play" : "pause"} size={20} color={COLORS.primary} />
          </TouchableOpacity>
        </View>

        <View style={styles.commentaryContainer}>
          <Text style={styles.commentaryTitle}>Ball by Ball</Text>
          <ScrollView ref={commentaryScrollRef} style={styles.commentaryScroll} showsVerticalScrollIndicator={false}>
            {currentBalls.slice(-20).map((ball, index) => (
              <View key={index} style={styles.commentaryItem}>
                <View style={[styles.ballIndicator, { backgroundColor: getBallColor(ball) }]}>
                  <Text style={styles.ballIndicatorText}>{ball.is_wicket ? 'W' : ball.outcome === '.' ? '•' : ball.runs}</Text>
                </View>
                <View style={styles.commentaryContent}>
                  <Text style={styles.commentaryOver}>{ball.over}.{ball.ball_in_over}</Text>
                  <Text style={styles.commentaryText}>{ball.bowler} to {ball.batter}: {ball.outcome}</Text>
                </View>
                <Text style={styles.commentaryScore}>{ball.total_after}/{ball.wickets_after}</Text>
              </View>
            ))}
          </ScrollView>
        </View>

        <View style={styles.progressContainer}>
          <View style={styles.progressBar}>
            <View style={[styles.progressFill, { width: `${(liveBallIndex / ballLog.length) * 100}%` }]} />
          </View>
          <Text style={styles.progressText}>{liveBallIndex}/{ballLog.length}</Text>
        </View>
      </View>
    );
  };

  // Scorecard Screen
  const renderScorecardScreen = () => {
    if (!matchResult) return null;
    const innings = selectedInnings === 1 ? matchResult.first_innings : matchResult.second_innings;

    return (
      <View style={styles.screenContainer}>
        <View style={styles.header}>
          <TouchableOpacity onPress={goBack} style={styles.headerButton}>
            <Ionicons name="arrow-back" size={24} color={COLORS.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Match Result</Text>
          <View style={{ width: 40 }} />
        </View>

        <ScrollView style={styles.scorecardContainer}>
          <View style={styles.resultBanner}>
            <Text style={styles.resultWinner}>{matchResult.result.winner}</Text>
            <Text style={styles.resultMargin}>won {matchResult.result.margin}</Text>
            <Text style={styles.tossInfo}>Toss: {matchResult.toss.winner} ({matchResult.toss.decision})</Text>
          </View>

          <View style={styles.scoreSummary}>
            <View style={styles.teamScoreCard}>
              <Text style={styles.teamScoreLabel}>{matchResult.first_innings.batting_team}</Text>
              <Text style={styles.teamScoreValue}>{matchResult.first_innings.runs}/{matchResult.first_innings.wickets}</Text>
              <Text style={styles.teamScoreOvers}>({matchResult.first_innings.overs} ov)</Text>
            </View>
            <View style={styles.teamScoreCard}>
              <Text style={styles.teamScoreLabel}>{matchResult.second_innings.batting_team}</Text>
              <Text style={styles.teamScoreValue}>{matchResult.second_innings.runs}/{matchResult.second_innings.wickets}</Text>
              <Text style={styles.teamScoreOvers}>({matchResult.second_innings.overs} ov)</Text>
            </View>
          </View>

          <View style={styles.inningsToggle}>
            <TouchableOpacity style={[styles.inningsTab, selectedInnings === 1 && styles.inningsTabActive]} onPress={() => setSelectedInnings(1)}>
              <Text style={[styles.inningsTabText, selectedInnings === 1 && styles.inningsTabTextActive]}>1st Innings</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.inningsTab, selectedInnings === 2 && styles.inningsTabActive]} onPress={() => setSelectedInnings(2)}>
              <Text style={[styles.inningsTabText, selectedInnings === 2 && styles.inningsTabTextActive]}>2nd Innings</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.scorecardSection}>
            <Text style={styles.scorecardSectionTitle}>{innings.batting_team} - Batting</Text>
            <View style={styles.scorecardHeader}>
              <Text style={[styles.scorecardHeaderCell, { flex: 2.5 }]}>Batter</Text>
              <Text style={styles.scorecardHeaderCell}>R</Text>
              <Text style={styles.scorecardHeaderCell}>B</Text>
              <Text style={styles.scorecardHeaderCell}>4s</Text>
              <Text style={styles.scorecardHeaderCell}>6s</Text>
              <Text style={styles.scorecardHeaderCell}>SR</Text>
            </View>
            {innings.batters.map((batter, index) => (
              <View key={index} style={styles.scorecardRow}>
                <View style={{ flex: 2.5 }}>
                  <Text style={styles.batterName}>{batter.name}</Text>
                  <Text style={styles.dismissalText}>{batter.is_out ? batter.dismissal : 'not out'}</Text>
                </View>
                <Text style={[styles.scorecardCell, batter.runs >= 50 && styles.highlightScore]}>{batter.runs}</Text>
                <Text style={styles.scorecardCell}>{batter.balls}</Text>
                <Text style={styles.scorecardCell}>{batter.fours}</Text>
                <Text style={styles.scorecardCell}>{batter.sixes}</Text>
                <Text style={styles.scorecardCell}>{batter.strike_rate.toFixed(0)}</Text>
              </View>
            ))}
            <View style={styles.totalRow}>
              <Text style={styles.totalLabel}>Total</Text>
              <Text style={styles.totalValue}>{innings.runs}/{innings.wickets} ({innings.overs} ov)</Text>
            </View>
          </View>

          <View style={styles.scorecardSection}>
            <Text style={styles.scorecardSectionTitle}>{innings.bowling_team} - Bowling</Text>
            <View style={styles.scorecardHeader}>
              <Text style={[styles.scorecardHeaderCell, { flex: 2.5 }]}>Bowler</Text>
              <Text style={styles.scorecardHeaderCell}>O</Text>
              <Text style={styles.scorecardHeaderCell}>M</Text>
              <Text style={styles.scorecardHeaderCell}>R</Text>
              <Text style={styles.scorecardHeaderCell}>W</Text>
              <Text style={styles.scorecardHeaderCell}>Eco</Text>
            </View>
            {innings.bowlers.map((bowler, index) => (
              <View key={index} style={styles.scorecardRow}>
                <Text style={[styles.bowlerName, { flex: 2.5 }]}>{bowler.name}</Text>
                <Text style={styles.scorecardCell}>{bowler.overs}</Text>
                <Text style={styles.scorecardCell}>{bowler.maidens}</Text>
                <Text style={styles.scorecardCell}>{bowler.runs}</Text>
                <Text style={[styles.scorecardCell, bowler.wickets >= 3 && styles.highlightScore]}>{bowler.wickets}</Text>
                <Text style={styles.scorecardCell}>{bowler.economy.toFixed(1)}</Text>
              </View>
            ))}
          </View>

          <TouchableOpacity style={styles.playAgainButton} onPress={() => { setMatchResult(null); navigateTo('home'); }}>
            <Ionicons name="refresh" size={20} color="#fff" />
            <Text style={styles.playAgainButtonText}>New Match</Text>
          </TouchableOpacity>
        </ScrollView>
      </View>
    );
  };

  // History Screen
  const renderHistoryScreen = () => (
    <View style={styles.screenContainer}>
      <View style={styles.header}>
        <TouchableOpacity onPress={goBack} style={styles.headerButton}>
          <Ionicons name="arrow-back" size={24} color={COLORS.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Match History</Text>
        {matchHistory.length > 0 && (
          <TouchableOpacity onPress={clearMatchHistory} style={styles.headerButton}>
            <Ionicons name="trash-outline" size={22} color={COLORS.danger} />
          </TouchableOpacity>
        )}
        {matchHistory.length === 0 && <View style={{ width: 40 }} />}
      </View>

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={COLORS.primary} />
        </View>
      ) : matchHistory.length === 0 ? (
        <View style={styles.emptyState}>
          <Ionicons name="time-outline" size={64} color={COLORS.textLight} />
          <Text style={styles.emptyStateText}>No matches played yet</Text>
          <Text style={styles.emptyStateSubtext}>Your match history will appear here</Text>
        </View>
      ) : (
        <FlatList
          data={matchHistory}
          keyExtractor={item => item.id}
          contentContainerStyle={{ padding: 16 }}
          renderItem={({ item }) => (
            <TouchableOpacity style={styles.historyCard} onPress={() => viewHistoryMatch(item)}>
              <View style={styles.historyCardHeader}>
                <Text style={styles.historyDate}>{formatDate(item.created_at)}</Text>
                <TouchableOpacity onPress={() => replayHistoryMatch(item)} style={styles.replayBtn}>
                  <Ionicons name="play-circle-outline" size={20} color={COLORS.primary} />
                </TouchableOpacity>
              </View>
              <View style={styles.historyTeams}>
                <View style={styles.historyTeam}>
                  <Text style={styles.historyTeamName}>{item.team1_name}</Text>
                  <Text style={styles.historyTeamScore}>{item.team1_score}/{item.team1_wickets}</Text>
                </View>
                <Text style={styles.historyVs}>vs</Text>
                <View style={styles.historyTeam}>
                  <Text style={styles.historyTeamName}>{item.team2_name}</Text>
                  <Text style={styles.historyTeamScore}>{item.team2_score}/{item.team2_wickets}</Text>
                </View>
              </View>
              <Text style={styles.historyResult}>{item.winner} won {item.margin}</Text>
            </TouchableOpacity>
          )}
        />
      )}
    </View>
  );

  // History Detail (Replay Scorecard)
  const renderHistoryDetailScreen = () => {
    if (!matchResult) return null;
    return renderScorecardScreen();
  };

  // Loading
  if (loading && !players.length) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="dark-content" backgroundColor={COLORS.background} />
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={COLORS.primary} />
          <Text style={styles.loadingText}>Loading players...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="dark-content" backgroundColor={COLORS.background} />
      {currentScreen === 'home' && renderHomeScreen()}
      {currentScreen === 'draftSetup' && renderDraftSetupScreen()}
      {currentScreen === 'draft' && renderDraftScreen()}
      {currentScreen === 'battingOrder' && renderBattingOrderScreen()}
      {currentScreen === 'live' && renderLiveScreen()}
      {currentScreen === 'scorecard' && renderScorecardScreen()}
      {currentScreen === 'history' && renderHistoryScreen()}
      {currentScreen === 'historyDetail' && renderHistoryDetailScreen()}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  loadingText: { color: COLORS.textSecondary, marginTop: 16, fontSize: 16 },
  screenContainer: { flex: 1 },
  screenContent: { paddingBottom: 40 },
  
  // Header
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 14, backgroundColor: COLORS.card, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  headerButton: { width: 40, height: 40, justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 18, fontWeight: '600', color: COLORS.text },
  skipText: { color: COLORS.primary, fontSize: 15, fontWeight: '500' },

  // Home
  heroSection: { alignItems: 'center', paddingVertical: 36, paddingHorizontal: 20, backgroundColor: COLORS.card, marginBottom: 16 },
  heroTitle: { fontSize: 28, fontWeight: '700', color: COLORS.text, marginTop: 12 },
  heroSubtitle: { fontSize: 16, color: COLORS.primary, marginTop: 4, fontWeight: '500' },
  actionButtons: { paddingHorizontal: 16, gap: 10 },
  primaryButton: { backgroundColor: COLORS.primary, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 15, borderRadius: 12, gap: 8 },
  primaryButtonText: { fontSize: 16, fontWeight: '600', color: '#fff' },
  buttonRow: { flexDirection: 'row', gap: 10 },
  secondaryButtonHalf: { flex: 1, backgroundColor: COLORS.card, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border, gap: 6 },
  secondaryButtonText: { fontSize: 14, fontWeight: '500', color: COLORS.text },
  outlineButton: { backgroundColor: COLORS.card, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.primary, gap: 8 },
  outlineButtonText: { fontSize: 14, fontWeight: '500', color: COLORS.primary },
  statsCard: { backgroundColor: COLORS.card, marginHorizontal: 16, marginTop: 20, borderRadius: 16, padding: 20, borderWidth: 1, borderColor: COLORS.border },
  statsTitle: { fontSize: 14, color: COLORS.textSecondary, marginBottom: 14, fontWeight: '500' },
  statsRow: { flexDirection: 'row', justifyContent: 'space-around' },
  statItem: { alignItems: 'center' },
  statNumber: { fontSize: 26, fontWeight: '700', color: COLORS.primary },
  statLabel: { fontSize: 12, color: COLORS.textSecondary, marginTop: 4 },

  // Draft Setup
  setupContainer: { flex: 1, padding: 16 },
  setupSectionTitle: { fontSize: 16, fontWeight: '600', color: COLORS.text, marginBottom: 12, marginTop: 8 },
  optionCards: { flexDirection: 'row', gap: 12 },
  optionCard: { flex: 1, backgroundColor: COLORS.card, borderRadius: 12, padding: 16, alignItems: 'center', borderWidth: 2, borderColor: COLORS.border },
  optionCardActive: { borderColor: COLORS.primary, backgroundColor: COLORS.primaryLight },
  optionCardTitle: { fontSize: 16, fontWeight: '600', color: COLORS.textSecondary, marginTop: 8 },
  optionCardTitleActive: { color: COLORS.primary },
  optionCardDesc: { fontSize: 12, color: COLORS.textSecondary, marginTop: 4, textAlign: 'center' },
  difficultyOptions: { flexDirection: 'row', gap: 10 },
  difficultyChip: { flex: 1, backgroundColor: COLORS.card, paddingVertical: 12, borderRadius: 10, alignItems: 'center', borderWidth: 1, borderColor: COLORS.border },
  difficultyChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  difficultyChipText: { fontSize: 14, fontWeight: '500', color: COLORS.textSecondary },
  difficultyChipTextActive: { color: '#fff' },
  difficultyInfo: { backgroundColor: COLORS.primaryLight, padding: 12, borderRadius: 8, marginTop: 12 },
  difficultyInfoText: { fontSize: 13, color: COLORS.primary, textAlign: 'center' },
  teamNameInputs: { gap: 12 },
  teamNameRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  teamNameLabel: { fontSize: 14, color: COLORS.textSecondary, fontWeight: '500', width: 80 },
  teamNameInput: { flex: 1, backgroundColor: COLORS.card, borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 10, fontSize: 15, color: COLORS.text },
  startDraftButton: { backgroundColor: COLORS.primary, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 14, borderRadius: 12, marginTop: 24, gap: 8 },
  startDraftButtonText: { fontSize: 16, fontWeight: '600', color: '#fff' },

  // Draft
  draftContainer: { flex: 1, padding: 16 },
  teamCard: { backgroundColor: COLORS.card, borderRadius: 16, padding: 16, marginBottom: 14, borderWidth: 1, borderColor: COLORS.border },
  teamHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  teamHeaderRight: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  teamName: { fontSize: 17, fontWeight: '600', color: COLORS.text },
  teamCount: { fontSize: 14, color: COLORS.primary, fontWeight: '600' },
  autoPickBtn: { padding: 6 },
  playerChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  playerChip: { backgroundColor: COLORS.primaryLight, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20, flexDirection: 'row', alignItems: 'center', gap: 6 },
  playerChipReadonly: { backgroundColor: COLORS.background, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20 },
  playerChipText: { color: COLORS.text, fontSize: 13, fontWeight: '500' },
  addPlayerChip: { backgroundColor: COLORS.card, borderWidth: 1.5, borderColor: COLORS.primary, borderStyle: 'dashed', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, flexDirection: 'row', alignItems: 'center', gap: 4 },
  addPlayerText: { color: COLORS.primary, fontSize: 13, fontWeight: '500' },
  aiTeamSection: { minHeight: 60 },
  aiThinkingBox: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, paddingVertical: 12, marginTop: 8 },
  aiThinkingText: { fontSize: 14, color: COLORS.primary, fontStyle: 'italic' },
  aiReasoningBox: { backgroundColor: COLORS.primaryLight, padding: 10, borderRadius: 8, marginTop: 8 },
  aiReasoningText: { fontSize: 12, color: COLORS.primary, fontStyle: 'italic' },
  aiHintText: { fontSize: 13, color: COLORS.textSecondary, textAlign: 'center', fontStyle: 'italic', marginTop: 8 },
  generateAIButton: { backgroundColor: COLORS.primary, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 12, borderRadius: 10, gap: 8, marginTop: 8 },
  generateAIButtonText: { fontSize: 14, fontWeight: '600', color: '#fff' },
  proceedButton: { backgroundColor: COLORS.primary, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 14, borderRadius: 12, marginTop: 8, gap: 8 },
  proceedButtonText: { fontSize: 15, fontWeight: '600', color: '#fff' },
  disabledButton: { opacity: 0.5 },

  // Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  modalContent: { backgroundColor: COLORS.card, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: '90%', paddingBottom: 20 },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 20, paddingVertical: 16, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  modalTitle: { fontSize: 17, fontWeight: '600', color: COLORS.text, flex: 1 },
  modalCloseBtn: { padding: 4 },
  searchContainer: { flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.background, marginHorizontal: 16, marginTop: 12, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 12, gap: 10 },
  searchInput: { flex: 1, fontSize: 15, color: COLORS.text, paddingVertical: 0 },
  filterToggle: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingVertical: 12 },
  filterToggleText: { fontSize: 14, color: COLORS.textSecondary, fontWeight: '500' },
  filtersContainer: { paddingHorizontal: 16, paddingBottom: 8 },
  filterLabel: { fontSize: 12, color: COLORS.textSecondary, marginBottom: 8, marginLeft: 4, fontWeight: '500' },
  filterScroll: { marginBottom: 12 },
  filterChip: { backgroundColor: COLORS.background, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, marginRight: 8 },
  filterChipActive: { backgroundColor: COLORS.primary },
  filterChipText: { color: COLORS.textSecondary, fontSize: 13, fontWeight: '500' },
  filterChipTextActive: { color: '#fff' },
  resultCount: { fontSize: 12, color: COLORS.textSecondary, paddingHorizontal: 20, paddingBottom: 8 },
  playerList: { flex: 1 },
  playerListItem: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 20, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  playerListItemSelected: { backgroundColor: COLORS.primaryLight },
  playerListItemDisabled: { opacity: 0.4 },
  playerInfo: { flex: 1 },
  playerName: { fontSize: 15, fontWeight: '500', color: COLORS.text },
  highlightedText: { backgroundColor: '#FFF3CD', color: COLORS.text },
  playerMeta: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
  playerStats: { alignItems: 'flex-end', marginRight: 12 },
  playerStat: { fontSize: 11, color: COLORS.textSecondary },

  // Batting Order
  orderToggle: { flexDirection: 'row', backgroundColor: COLORS.background, marginHorizontal: 16, marginTop: 12, borderRadius: 10, padding: 4 },
  orderTab: { flex: 1, paddingVertical: 10, alignItems: 'center', borderRadius: 8 },
  orderTabActive: { backgroundColor: COLORS.card },
  orderTabText: { fontSize: 14, fontWeight: '500', color: COLORS.textSecondary },
  orderTabTextActive: { color: COLORS.text },
  orderContainer: { flex: 1, padding: 16 },
  orderHint: { fontSize: 13, color: COLORS.textSecondary, marginBottom: 12, textAlign: 'center' },
  orderItem: { flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.card, borderRadius: 10, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  orderPosition: { width: 28, height: 28, borderRadius: 14, backgroundColor: COLORS.primaryLight, justifyContent: 'center', alignItems: 'center' },
  orderPositionText: { fontSize: 13, fontWeight: '600', color: COLORS.primary },
  orderPlayerInfo: { flex: 1, marginLeft: 12 },
  orderPlayerName: { fontSize: 14, fontWeight: '500', color: COLORS.text },
  orderPlayerRole: { fontSize: 12, color: COLORS.textSecondary },
  orderControls: { flexDirection: 'column', gap: 2 },
  orderBtn: { padding: 4 },
  orderBtnDisabled: { opacity: 0.3 },
  orderActions: { flexDirection: 'row', gap: 10, padding: 16, borderTopWidth: 1, borderTopColor: COLORS.border },
  simButtonOutline: { flex: 1, backgroundColor: COLORS.card, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 14, borderRadius: 12, borderWidth: 1, borderColor: COLORS.primary, gap: 6 },
  simButtonOutlineText: { fontSize: 15, fontWeight: '600', color: COLORS.primary },
  simButton: { flex: 1, backgroundColor: COLORS.primary, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 14, borderRadius: 12, gap: 6 },
  simButtonText: { fontSize: 15, fontWeight: '600', color: '#fff' },

  // Live
  liveScoreContainer: { backgroundColor: COLORS.card, paddingVertical: 20, alignItems: 'center', borderBottomWidth: 1, borderBottomColor: COLORS.border },
  liveTeamName: { fontSize: 14, color: COLORS.textSecondary, fontWeight: '500' },
  liveScoreRow: { flexDirection: 'row', alignItems: 'baseline', marginTop: 4 },
  liveScore: { fontSize: 42, fontWeight: '700', color: COLORS.text },
  liveOvers: { fontSize: 16, color: COLORS.textSecondary, marginLeft: 8 },
  liveTarget: { fontSize: 13, color: COLORS.primary, marginTop: 6, fontWeight: '500' },
  currentPlayersCard: { backgroundColor: COLORS.card, marginHorizontal: 16, marginTop: 12, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: COLORS.border },
  currentPlayerRow: { flexDirection: 'row', justifyContent: 'space-between' },
  currentPlayer: { flex: 1 },
  currentPlayerLabel: { fontSize: 11, color: COLORS.textSecondary, fontWeight: '500' },
  currentPlayerName: { fontSize: 14, color: COLORS.text, fontWeight: '600', marginTop: 2 },
  bowlerRow: { marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderTopColor: COLORS.border },
  speedControls: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 10, paddingVertical: 12, backgroundColor: COLORS.card, marginHorizontal: 16, marginTop: 12, borderRadius: 12 },
  speedButton: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20, backgroundColor: COLORS.background },
  speedButtonActive: { backgroundColor: COLORS.primary },
  speedButtonText: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary },
  speedButtonTextActive: { color: '#fff' },
  pauseButton: { width: 40, height: 40, borderRadius: 20, backgroundColor: COLORS.background, justifyContent: 'center', alignItems: 'center', marginLeft: 10 },
  commentaryContainer: { flex: 1, backgroundColor: COLORS.card, marginHorizontal: 16, marginTop: 12, borderRadius: 12, padding: 14 },
  commentaryTitle: { fontSize: 14, fontWeight: '600', color: COLORS.text, marginBottom: 10 },
  commentaryScroll: { flex: 1 },
  commentaryItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  ballIndicator: { width: 28, height: 28, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  ballIndicatorText: { fontSize: 12, fontWeight: '700', color: '#fff' },
  commentaryContent: { flex: 1, marginLeft: 10 },
  commentaryOver: { fontSize: 11, color: COLORS.textSecondary, fontWeight: '500' },
  commentaryText: { fontSize: 13, color: COLORS.text, marginTop: 1 },
  commentaryScore: { fontSize: 13, fontWeight: '600', color: COLORS.text },
  progressContainer: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, gap: 10 },
  progressBar: { flex: 1, height: 4, backgroundColor: COLORS.border, borderRadius: 2, overflow: 'hidden' },
  progressFill: { height: '100%', backgroundColor: COLORS.primary, borderRadius: 2 },
  progressText: { fontSize: 12, color: COLORS.textSecondary },

  // Scorecard
  scorecardContainer: { flex: 1 },
  resultBanner: { backgroundColor: COLORS.primary, padding: 20, alignItems: 'center' },
  resultWinner: { fontSize: 22, fontWeight: '700', color: '#fff' },
  resultMargin: { fontSize: 16, color: 'rgba(255,255,255,0.9)', marginTop: 4 },
  tossInfo: { fontSize: 12, color: 'rgba(255,255,255,0.7)', marginTop: 8 },
  scoreSummary: { flexDirection: 'row', padding: 16, gap: 12 },
  teamScoreCard: { flex: 1, backgroundColor: COLORS.card, borderRadius: 12, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: COLORS.border },
  teamScoreLabel: { fontSize: 12, color: COLORS.textSecondary, fontWeight: '500' },
  teamScoreValue: { fontSize: 26, fontWeight: '700', color: COLORS.text, marginTop: 4 },
  teamScoreOvers: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
  inningsToggle: { flexDirection: 'row', backgroundColor: COLORS.background, marginHorizontal: 16, marginBottom: 12, borderRadius: 10, padding: 4 },
  inningsTab: { flex: 1, paddingVertical: 10, alignItems: 'center', borderRadius: 8 },
  inningsTabActive: { backgroundColor: COLORS.card },
  inningsTabText: { fontSize: 14, fontWeight: '500', color: COLORS.textSecondary },
  inningsTabTextActive: { color: COLORS.text },
  scorecardSection: { backgroundColor: COLORS.card, marginHorizontal: 16, marginBottom: 12, borderRadius: 12, overflow: 'hidden', borderWidth: 1, borderColor: COLORS.border },
  scorecardSectionTitle: { fontSize: 14, fontWeight: '600', color: COLORS.text, padding: 12, backgroundColor: COLORS.background },
  scorecardHeader: { flexDirection: 'row', paddingHorizontal: 12, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  scorecardHeaderCell: { flex: 1, fontSize: 11, fontWeight: '600', color: COLORS.textSecondary, textAlign: 'center' },
  scorecardRow: { flexDirection: 'row', paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: COLORS.border, alignItems: 'center' },
  batterName: { fontSize: 13, fontWeight: '500', color: COLORS.text },
  dismissalText: { fontSize: 10, color: COLORS.textSecondary, marginTop: 2 },
  bowlerName: { fontSize: 13, fontWeight: '500', color: COLORS.text },
  scorecardCell: { flex: 1, fontSize: 13, color: COLORS.text, textAlign: 'center' },
  highlightScore: { fontWeight: '700', color: COLORS.primary },
  totalRow: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 12, paddingVertical: 12, backgroundColor: COLORS.background },
  totalLabel: { fontSize: 14, fontWeight: '600', color: COLORS.text },
  totalValue: { fontSize: 14, fontWeight: '600', color: COLORS.primary },
  playAgainButton: { backgroundColor: COLORS.primary, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 14, borderRadius: 12, gap: 8, marginHorizontal: 16, marginVertical: 16 },
  playAgainButtonText: { fontSize: 15, fontWeight: '600', color: '#fff' },

  // History
  emptyState: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 40 },
  emptyStateText: { fontSize: 18, fontWeight: '600', color: COLORS.textSecondary, marginTop: 16 },
  emptyStateSubtext: { fontSize: 14, color: COLORS.textLight, marginTop: 4 },
  historyCard: { backgroundColor: COLORS.card, borderRadius: 12, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border },
  historyCardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  historyDate: { fontSize: 12, color: COLORS.textSecondary },
  replayBtn: { padding: 4 },
  historyTeams: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  historyTeam: { flex: 1, alignItems: 'center' },
  historyTeamName: { fontSize: 14, fontWeight: '600', color: COLORS.text },
  historyTeamScore: { fontSize: 20, fontWeight: '700', color: COLORS.primary, marginTop: 4 },
  historyVs: { fontSize: 12, color: COLORS.textSecondary, marginHorizontal: 10 },
  historyResult: { fontSize: 13, color: COLORS.success, fontWeight: '500', textAlign: 'center', marginTop: 12 },
});
