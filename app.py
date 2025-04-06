from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
import os
import random

app = Flask(__name__)
app.secret_key = os.urandom(24) # For session management, though not strictly needed for this simple state

# Configuration
QUESTIONS_FILE = 'trivia_questions.json'
STATE_FILE = 'game_state.json'

# --- State Persistence ---
def save_state(state):
    """Saves the current game state to a JSON file."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=4)
    except IOError as e:
        print(f"Error saving state: {e}")

def load_state():
    """Loads the game state from a JSON file, or returns default state (with shuffled questions)."""
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, IOError) as e:
        print(f"Error loading state ({e}), using default state.")
        # Default initial state if file not found or invalid
        default_questions = load_questions() # Load fresh questions
        random.shuffle(default_questions)    # Shuffle them immediately
        return {
            'teams': {},
            'current_question': None,
            'current_answer': None,
            'state': 'lobby', # lobby, question_displayed, answer_revealed
            'questions': default_questions, # Use shuffled list
            'used_questions_indices': []
        }

# --- Game Logic Helpers ---
def load_questions():
    """Loads questions from the JSON file."""
    try:
        with open(QUESTIONS_FILE, 'r') as f:
            all_questions_data = json.load(f)
            questions = []
            for category, q_list in all_questions_data.items():
                for q in q_list:
                    q['category'] = category # Add category info to each question
                    questions.append(q)
            return questions
    except FileNotFoundError:
        print(f"Error: {QUESTIONS_FILE} not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {QUESTIONS_FILE}.")
        return []

# --- Initialize Game State ---
# Load state from file or use default
game_state = load_state()

# Ensure questions are loaded AND SHUFFLED if the state was loaded without them 
# (e.g., if questions file changed or state file was from older version/missing questions key)
if not game_state.get('questions'):
    print("Loaded state missing questions, reloading and shuffling...")
    reloaded_questions = load_questions()
    random.shuffle(reloaded_questions) # Shuffle freshly loaded questions
    game_state['questions'] = reloaded_questions
    if not game_state['questions']:
         print("CRITICAL ERROR: No questions loaded. Trivia cannot proceed.")
    # Save the state now that we've potentially added shuffled questions
    save_state(game_state) 

# --- Routes ---
@app.route('/')
def index():
    """Displays the main trivia control page."""
    sorted_teams = sorted(game_state['teams'].items(), key=lambda item: item[1], reverse=True)
    return render_template('index.html', game_state=game_state, sorted_teams=sorted_teams)

@app.route('/add_team', methods=['POST'])
def add_team():
    """Adds a new team."""
    team_name = request.form.get('team_name')
    if team_name and team_name not in game_state['teams']:
        game_state['teams'][team_name] = 0
        save_state(game_state) # Save state after modification
        print(f"Added team: {team_name}")
    return redirect(url_for('index'))

@app.route('/remove_team', methods=['POST'])
def remove_team():
    team_name = request.form.get('team_name')
    if team_name in game_state['teams']:
        del game_state['teams'][team_name]
        save_state(game_state) # Save state after modification
    return redirect(url_for('index'))

@app.route('/start_game')
def start_game():
    """Starts the game by moving to the first question."""
    if game_state['state'] == 'lobby' and game_state['questions']:
        game_state['current_question_index'] = 0
        question_data = game_state['questions'][0]
        game_state['current_category'] = question_data['category']
        game_state['current_question'] = question_data['question']
        game_state['current_answer'] = question_data['answer']
        game_state['state'] = 'question_displayed'
        print("Game started.")
    return redirect(url_for('index'))

@app.route('/next_question')
def next_question():
    """Moves to the next question (or skips)."""
    # Allow moving next from lobby, answer revealed, OR question displayed (for skip)
    if game_state['state'] in ['lobby', 'answer_revealed', 'question_displayed'] and game_state['questions']:
        next_index = game_state['current_question_index'] + 1
        if next_index < len(game_state['questions']):
            game_state['current_question_index'] = next_index
            question_data = game_state['questions'][next_index]
            game_state['current_category'] = question_data['category']
            game_state['current_question'] = question_data['question']
            game_state['current_answer'] = question_data['answer']
            game_state['state'] = 'question_displayed'
            print(f"Moved to question {next_index + 1}")
        else:
            game_state['current_category'] = "Game Over"
            game_state['current_question'] = "No more questions!"
            game_state['current_answer'] = "-"
            game_state['state'] = 'lobby'
            print("End of questions reached.")
    # Always redirect back to index after attempting next/skip
    return redirect(url_for('index'))

@app.route('/reveal_answer')
def reveal_answer():
    """Reveals the answer to the current question."""
    if game_state['state'] == 'question_displayed':
        game_state['state'] = 'answer_revealed'
        save_state(game_state) # Save state after revealing answer
        print("Answer revealed.")
    return redirect(url_for('index'))

@app.route('/update_score', methods=['POST'])
def update_score():
    """Updates the score for a specific team via Fetch API."""
    data = request.get_json()
    team_name = data.get('team_name')
    try:
        points = int(data.get('points', 0))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid points value'}), 400

    if team_name in game_state['teams']:
        game_state['teams'][team_name] += points
        save_state(game_state) # Save state after modification
        return jsonify({'success': True, 'team_name': team_name, 'new_score': game_state['teams'][team_name]})
    else:
        return jsonify({'success': False, 'error': 'Team not found'}), 404

@app.route('/reset_game')
def reset_game():
    """Resets the game questions and scores, keeps teams."""
    global game_state
    # Preserve existing teams but reset scores
    current_teams = game_state.get('teams', {}) # Get existing teams or empty dict if none
    for team in current_teams:
        current_teams[team] = 0 # Reset score to 0

    # Reset to the default state structure, keeping modified teams
    loaded_questions = load_questions() # Load fresh questions
    random.shuffle(loaded_questions) # Shuffle them for the new game
    game_state = {
        'teams': current_teams, # Use the preserved teams with reset scores
        'current_question': None,
        'current_answer': None,
        'state': 'lobby',
        'questions': loaded_questions, # Use the shuffled list
        'used_questions_indices': []
    }
    save_state(game_state) # Save the reset and shuffled state
    print("Game reset successfully (scores reset, teams kept) with shuffled questions.")
    return redirect(url_for('index'))

@app.route('/reset_teams')
def reset_teams():
    """Resets the teams and scores completely."""
    game_state['teams'] = {}
    print("Teams and scores reset.")
    # Also reset game state to be safe
    reset_game()
    return redirect(url_for('index'))

if __name__ == '__main__':
    if not os.path.exists('templates'):
        os.makedirs('templates')
    # Check if index.html exists, if not create a basic one
    if not os.path.exists('templates/index.html'):
        with open('templates/index.html', 'w') as f:
            f.write('<h1>Template Missing</h1><p>Run the script again to generate the template.</p>')
        print("Created basic templates/index.html. Please run again to populate.")
    else:
        # Check if JSON file exists
        if not os.path.exists(QUESTIONS_FILE):
             print(f"Error: {QUESTIONS_FILE} not found! Cannot start app.")
        else:
            app.run(host='0.0.0.0', threaded=False, debug=True)
