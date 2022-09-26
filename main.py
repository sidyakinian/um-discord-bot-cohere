from ast import Constant
import os
from dotenv import load_dotenv

import discord
from discord.ext import commands

from managers.FirebaseManager import FirebaseManager
from managers.AIManager import AIManager
from managers.QuestionAnswerer import QuestionAnswerer
from managers.MessageSender import MessageSender

from constants.Miscellaneous import Miscellaneous
from constants.States import States

import sentry_sdk
import asyncio
import string

load_dotenv()
DISCORD_BOT_TOKEN = os.environ['DISCORD_BOT_TOKEN']


intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)
bot.remove_command('help')  # Remove default help command

firebase_manager = FirebaseManager()
ai_manager = AIManager()
question_answerer = QuestionAnswerer(firebase_manager, ai_manager)
message_sender = MessageSender(firebase_manager)

sentry_sdk.init(
    dsn="https://3f814274726a4857b55765cb3a30923d@o1366840.ingest.sentry.io/6666956",

    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production.
    traces_sample_rate=1.0
)

# Puzzles I'm using
# 1. 🔫 Fatal shot
# 2. 👠 Mysterious shoe
# 3. 📚 Book at the library
# 4. 🏨 Expensive hotel
# 5. 👨🏼‍🦰 Man on the elevator


# Members

@bot.event
async def on_ready():
    print('We have logged in as discord bot')


@bot.event
async def on_member_join(member):
    await firebase_manager.add_user_state(str(member.id))
    await member.send('''
Hi! Welcome to Um. Um is an AI chatbot puzzle game.

Here's how to play:

1. You're presented with a strange situation, which is part of a larger story.
2. You make guesses to better understand the full story. The bot will tell you if your guess is correct, incorrect, or irrelevant to the solution.
3. Once you think you got the full story, submit a solution and the bot will let you know if you got it right!

(Please type `!next` to see an example)''')
    # Wake up the model
    await ai_manager.complete_prompt(f"mnli hypothesis: wake up premise: wake up")


@bot.event
async def on_member_leave(member):
    await firebase_manager.delete_user_state(str(member.id))


# Messages

@bot.event
async def on_message(message):
    print('Message received!')

    if message.author.bot:
        return

    await firebase_manager.log_message(str(message.author.id), message.content, True)
    state_name, puzzle_id, hints_given = await firebase_manager.state(str(message.author.id))
    if state_name.split('_')[0] == 'tutorial':
        await handle_tutorial_message(message, state_name, puzzle_id, hints_given)
        return

    if message.content[0] == '!':
        command = message.content.split(' ')[0][1:]
        if command in Miscellaneous.list_of_commands:
            await bot.process_commands(message)
        else:
            await message_sender.send_message_from_author(message.author, "Invalid command. Please type `!help` for a list of commands.")
        return

    if puzzle_id == -1:
        # No puzzle
        await message_sender.send_message_from_author(message.author, f"Please select puzzle first. Type `!puzzles` to see available puzzles.")
    else:
        # Normal puzzle
        # ctx = await bot.get_context(message)
        # TODO: send message when the model is taking a while to load
        # TODO: add typing context, but properly
        reply = await question_answerer.answer_question(puzzle_id, message.content)
        if reply is not None:
            await message_sender.send_message_from_author(message.author, reply)
        else:
            await message_sender.send_message_from_author(message.author, "Sorry, something went wrong :(")

# Commands

@bot.command(name='puzzles')
async def list_puzzles(ctx):
    print('Puzzles command received!')
    puzzles_doc_data = await firebase_manager.all_puzzles()
    puzzle_list_string = ''
    for puzzle_doc_data in puzzles_doc_data:
        id = puzzle_doc_data['id']
        # Limit to puzzles with ids 1 to 7 for now
        if id > 7:
            continue
        title = puzzle_doc_data['title']
        puzzle_string = f'{id}: {title}'
        puzzle_list_string += '\n' + puzzle_string
    await message_sender.send_message_from_ctx(ctx, f'''
Here are all the puzzles we have:
{puzzle_list_string}

To play a puzzle, type `!play x`, where `x` is the number of the puzzle. For example, `!play 1`.''')


@bot.command(name='play')
async def play(ctx, puzzle_id):
    state_name, current_puzzle_id, hints_given = await firebase_manager.state(str(ctx.author.id))
    if state_name == "playing":
        await message_sender.send_message_from_ctx(ctx, f"Already playing puzzle {current_puzzle_id}! Type `!quit` to quit puzzle.")
        return
    if int(puzzle_id) > 7:
        await message_sender.send_message_from_ctx(ctx, "No puzzle with this number! Please type `!puzzles` to see available puzzles.")
        return
    try:
        puzzle_data = await firebase_manager.puzzle_data(puzzle_id)
        await firebase_manager.set_to_playing(str(ctx.author.id), int(puzzle_id))
        title = puzzle_data['title']
        problem = puzzle_data['problem']
        await message_sender.send_message_from_ctx(ctx, f'{title}\n\n{problem}')
    except Exception as e:
        await message_sender.send_message_from_ctx(ctx, "No puzzle with this number! Please type `!puzzles` to see available puzzles.")
        return


@bot.command(name='hint')
async def hint(ctx):
    state_name, puzzle_id, hints_given = await firebase_manager.state(str(ctx.author.id))
    # TODO: Harcode a limit of 2 on hints, increase it later on
    if hints_given >= 2:
        await message_sender.send_message_from_ctx(ctx, "You have used all your hints!")
    if state_name == "playing":
        # Get hint
        puzzle_data = await firebase_manager.puzzle_data(puzzle_id)
        hint = puzzle_data['hints'][hints_given]
    
        # Increment hint
        await firebase_manager.increment_hint(str(ctx.author.id))

        # Send hint
        await message_sender.send_message_from_ctx(ctx, "Here's a hint:\n\n" + hint)
    else:
        await message_sender.send_message_from_ctx(ctx, "Not playing any puzzle right now. Please select a puzzle from `!puzzles` first!")

@bot.command(name='submit')
async def submit(ctx):
    state_name, puzzle_id, hints_given = await firebase_manager.state(str(ctx.author.id))
    guess = ' '.join(ctx.message.content.split(' ')[1:])
    if state_name == "playing":
        is_solution_correct = await question_answerer.check_solution(puzzle_id, guess)
        if is_solution_correct:
            await message_sender.send_message_from_ctx(ctx, "Correct, you got it!!!🤩")
            await firebase_manager.set_to_idle(str(ctx.author.id))
        else:
            await message_sender.send_message_from_ctx(ctx, "Incorrect :( Try again!")
    else:
        await message_sender.send_message_from_ctx(ctx, "Not playing any puzzle right now. Please select a puzzle from `!puzzles` first!")

@bot.command(name='giveup')
async def giveup(ctx):
    state_name, puzzle_id, hints_given = await firebase_manager.state(str(ctx.author.id))
    if state_name == "playing":
        await message_sender.send_message_from_ctx(ctx, "Here is the solution:")
        puzzle_data = await firebase_manager.puzzle_data(puzzle_id)
        solution = puzzle_data['solution']
        await asyncio.sleep(1)
        await message_sender.send_message_from_ctx(ctx, solution)
    else:
        await message_sender.send_message_from_ctx(ctx, "Not playing any puzzle right now. Please select a puzzle from `!puzzles` first!")

@bot.command(name='quit')
async def quit(ctx):
    state_name, _, hints_given = await firebase_manager.state(str(ctx.author.id))
    if state_name == "idle":
        await message_sender.send_message_from_ctx(ctx, "Not playing any puzzle!")
    else:
        await firebase_manager.set_to_idle(str(ctx.author.id))
        await message_sender.send_message_from_ctx(ctx, "Quit playing puzzle.")

@bot.command(name='help')
async def help(ctx):
    await message_sender.send_message_from_ctx(ctx, """
Available commands:
`!puzzles` - Lists all available puzzles
`!play x` - Starts playing puzzle numbered `x`
`!hint` - Gives you a hint
`!submit` - Submits your solution
`!quit` - Quits playing puzzle
`!giveup` - Reveals the solution to the puzzle. Use sparingly :D
`!feedback` - Sends feedback to the developer, e. g. `!feedback I found a bug`. If you'd like a reply, please include your email or Discord username!
    """)

@bot.command(name='feedback')
async def feedback(ctx):
    feedback_message = ' '.join(ctx.message.content.split(' ')[1:])
    await firebase_manager.add_feedback(str(ctx.author.id), feedback_message)
    await ctx.send(f"Thanks for your feedback!🥰")


# Tutorial

def remove_punctuation(s):
    return s.translate(str.maketrans('', '', string.punctuation))

async def is_message_close(message, target_message):
    exactly_matches = remove_punctuation(message.lower()) == remove_punctuation(target_message.lower())
    inference_matches = await ai_manager.complete_prompt(f"mnli hypothesis: {target_message} premise: {message}") == 'entailment'
    return exactly_matches or inference_matches

# Precondition: only for states starting with 'tutorial'
async def handle_tutorial_message(message, state_name, puzzle_id, hints_given):
    async def answer_question(question):
        reply = await question_answerer.answer_question(puzzle_id, question)
        if reply is not None:
            await message_sender.send_message_from_author(message.author, reply)
        else:
            await message_sender.send_message_from_author(message.author, "Sorry, something went wrong :(")

    next_command = '!next'
    if state_name == States.tutorial_welcome:
        if message.content == next_command:
            await message_sender.send_message_from_author(message.author, '''
Here's an a simple example problem:

🪟 Lucky jumper

A person jumped from the windowsill and survived without a scratch completely unharmed.

(Type `!next`)''')
            await firebase_manager.set_to_tutorial(str(message.author.id), States.tutorial_example)
        else:
            await message_sender.send_message_from_author(message.author, 'Please follow the tutorial. Type `!next` to continue.')
    elif state_name == States.tutorial_example:
        if message.content == next_command:
            await message_sender.send_message_from_author(message.author, '''
Unusual, right? Usually jumping from a height would get you injured!

You can think of the full story as an iceberg. You're only presented with a small part, and by making guesses you need to discover what's underneath.

(Type `!next`)''', file=discord.File('./assets/iceberg.png'))
            await firebase_manager.set_to_tutorial(str(message.author.id), States.tutorial_iceberg)
        else:
            await message_sender.send_message_from_author(message.author, 'Please follow the tutorial. Type `!next` to continue.')
    elif state_name == States.tutorial_iceberg:
        if message.content == next_command:
            await message_sender.send_message_from_author(message.author, '''
Now try making guesses about the story to get more information. For example, try guessing "the person had a parachute".

(Type `The person had a parachute` or something similar)''')
            await firebase_manager.set_to_tutorial(str(message.author.id), States.tutorial_first_guess)
        else:
            await message_sender.send_message_from_author(message.author, 'Please follow the tutorial. Type `!next` to continue.')
    elif state_name == States.tutorial_first_guess:
        if await is_message_close(message.content, "The person had a parachute"):
            await answer_question(message.content)
            await asyncio.sleep(1)
            await message_sender.send_message_from_author(message.author, '''
Turns out the person didn't have a parachute! Now you know a bit more about the story.

There are many possible verions of what happened, but only one of them is right! Small guesses help you eliminate possibilities and move closer to the solution.

(Type `!next`)''', file=discord.File('./assets/possibility_tree.png'))
            await firebase_manager.set_to_tutorial(str(message.author.id), States.tutorial_possibility_tree)
        else:
            await message_sender.send_message_from_author(message.author, '''
Please try again. Type `The person had a parachute` or something similar.''')
    elif state_name == States.tutorial_possibility_tree:
        if message.content == next_command:
            await message_sender.send_message_from_author(message.author, '''
Sometimes a guess is irrelevant to the answer - it could be right or wrong and it doesn't affect the solution.

For example, try checking if the person was married.

(Type `The person was married` or something similar)''')
            await firebase_manager.set_to_tutorial(str(message.author.id), States.tutorial_irrelevant)
        else:
            await message_sender.send_message_from_author(message.author, 'Please follow the tutorial. Type `!next` to continue.')
    elif state_name == States.tutorial_irrelevant:
        if await is_message_close(message.content, "The person was married"):
            await answer_question(message.content)
            await asyncio.sleep(1)
            await message_sender.send_message_from_author(message.author, '''
Once you've made a few small guesses and feel like you know the full story, use `!submit` to submit your solution! Make sure your solution includes all important parts that explain what happened.

Try submitting a solution "The person was caught with a net".

(Please type `submit! The person was caught with a net` or something similar)''')
            await firebase_manager.set_to_tutorial(str(message.author.id), States.tutorial_submit)
        else:
            await message_sender.send_message_from_author(message.author, '''
Please try again. Type `the person was married` or something similar.''')
    elif state_name == States.tutorial_submit:
        if await is_message_close(message.content, "!submit The person was caught with a net"):
            await message_sender.send_message_from_author(message.author, 'Incorrect :( Please try again!')
            await asyncio.sleep(1)
            await message_sender.send_message_from_author(message.author, '''
This one is wrong, but you can try submitting your solution in a second!

If you get stuck, use hints! Hints are meant to be used often in this game. The vast majority of players only solve puzzles with hints - playing without hints is hard mode :)

(Type `!hint`)''')
            await firebase_manager.set_to_tutorial(str(message.author.id), States.tutorial_hints)
        else:
            await message_sender.send_message_from_author(message.author, 'Please follow the tutorial. Type `!next` to continue.')
    elif state_name == States.tutorial_hints:
        if message.content == '!hint':
            # Give hint
            puzzle_data = await firebase_manager.puzzle_data(puzzle_id)
            hint = puzzle_data['hints'][hints_given]
            await firebase_manager.increment_hint(str(message.author.id))
            await message_sender.send_message_from_author(message.author, "Here's a hint:\n\n" + hint)
            await asyncio.sleep(2)
            await message_sender.send_message_from_author(message.author, '''
One last thing: please agree to our privacy policy before using the bot. Tl;dr: is that to help improve our playing experience and teach the AI how to better check guesses, the bot can collect certain data, including commands you send to the bot, guesses, and submitted solutions.

**We don't collect your name, email, location, or any other identifiable information.** Please don't give the bot any personal information (the bot won't ask for it).

(Type `I agree` to agree to the privacy policy)''')
            await firebase_manager.set_to_tutorial(str(message.author.id), States.tutorial_privacy)
        else:
            await message_sender.send_message_from_author(message.author, 'Please follow the tutorial. Type `!hint` to continue.')
    elif state_name == States.tutorial_privacy:
        if await is_message_close(message.content, "I agree"):
            await message_sender.send_message_from_author(message.author, '''
Okay great! Now try solving the puzzle and `!submit` once you're ready! If you get stuck, use another hint.''')
            await firebase_manager.set_to_tutorial(str(message.author.id), States.tutorial_now_solve)
        else:
            await message_sender.send_message_from_author(message.author, '''Please type `I agree` to agree to the privacy policy.''')
    elif state_name == States.tutorial_now_solve:
        # Once correct, congratulate and move on to idle state
        if message.content.split(' ')[0] == '!submit':
            # Check submission
            guess = ' '.join(message.content.split(' ')[1:])
            is_solution_correct = await question_answerer.is_solution_correct(guess, puzzle_id)
            if is_solution_correct:
                await message_sender.send_message_from_author(message.author, "Correct, you got it!!!🤩")
                await firebase_manager.set_to_idle(str(message.author.id))
                await message_sender.send_message_from_author(message.author, """
Congrats on solving your first puzzle! Now you can type `!puzzles` to see all available puzzles and play them as you want! Good luck!

For a list of commands, type `!help`. If you have any feedback, please send it like this: `!feedback <feedback here>` Thanks!""")
                await firebase_manager.set_to_idle(str(message.author.id))
            else:
                await message_sender.send_message_from_author(message.author, "Incorrect :( Try again!")
        elif message.content.split(' ')[0] == '!hint':
            await message_sender.send_message_from_author(message.author, "Hint is not implemented yet! Please don't try again.")
        elif message.content[0] == '!':
            await message_sender.send_message_from_author(message.author, "Please follow tutorial.")
        else:
            # Answer question
            await answer_question(message.content)
    else:
        # TODO: log error in analytics
        print(f"Error: Unknown state {state_name}")
        pass


# Developer

@bot.command(name='_puzzle_data')
async def _puzzle_data(ctx):
    puzzle_id = int(ctx.message.content.split(' ')[1])
    puzzle_data = await firebase_manager.puzzle_data(puzzle_id)
    if puzzle_data:
        await message_sender.send_message_from_ctx(ctx, repr(puzzle_data))
    else:
        await message_sender.send_message_from_ctx(ctx, f'No puzzle with id {puzzle_id}')


@bot.command(name='_space')
async def _space(ctx):
    enter_string = ''.join(['\n'] * 40)
    await message_sender.send_message_from_ctx(ctx, f'.{enter_string}.')

@bot.command(name='_crash')
async def _crash(ctx):
    await message_sender.send_message_from_ctx(ctx, 'Crashing now...')
    division_by_zero = 1 / 0
    await message_sender.send_message_from_ctx(ctx, 'Did it crash?..')

@bot.command(name='_complete_prompt')
async def _complete_prompt(ctx):
    solution = ' '.join(ctx.message.content.split(' ')[1:])
    reply = await ai_manager.complete_prompt(solution)
    await message_sender.send_message_from_ctx(ctx, reply)
    

print('About to run bot...')

bot.run(DISCORD_BOT_TOKEN)