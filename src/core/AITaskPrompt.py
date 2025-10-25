# NOTE: User-specific preferences (Ian, Karleigh) are intentionally hardcoded here
# TODO: Future enhancement - migrate user preferences to database/web interface
# This includes:
# - TIME_WEIGHTS: User-specific task category preferences by time of day
# - EXAMPLES: User-specific task examples and preferences
# - Personal preferences (schedule, likes, etc.)
class AITaskPrompt:
    def __init__(self):
        
        # Time-based category weights for different users and time periods
        # TODO: Move to database/web interface - store per user in users collection
        self.TIME_WEIGHTS = {
            "Ian": {
                "morning": {"Work": 0, "Kids": 2, "Spouse": 3, "House": 1, "Self": 4},
                "workday": {"Work": 1, "Kids": 0, "Spouse": 2, "House": 10,"Self": 4},
                "evening": {"Work": 0, "Kids": 5, "Spouse": 4, "House": 2, "Self": 2},
                "weekend": {"Work": 0, "Kids": 3, "Spouse": 2, "House": 3, "Self": 1}
            },
            "Karleigh": {
                "morning": {"Work": 0, "Kids": 1, "Spouse": 4, "House": 1, "Self": 4},
                "workday": {"Work": 10,"Kids": 0, "Spouse": 2, "House": 0, "Self": 4},
                "evening": {"Work": 0, "Kids": 5, "Spouse": 4, "House": 2, "Self": 2},
                "weekend": {"Work": 1, "Kids": 3, "Spouse": 2, "House": 2, "Self": 1}
            },
            "default": {
                "morning": {"Work": 1, "Kids": 1, "Spouse": 1, "House": 1, "Self": 1},
                "workday": {"Work": 1, "Kids": 1, "Spouse": 1, "House": 1, "Self": 1},
                "evening": {"Work": 1, "Kids": 1, "Spouse": 1, "House": 1, "Self": 1},
                "weekend": {"Work": 1, "Kids": 1, "Spouse": 1, "House": 1, "Self": 1}
            }
        }

        self.SYSTEM_PROMPT = """
You are a creative assistant for a gamified task system between spouses, Ian and Karleigh.

Your job is to generate specific, real-life tasks for a given participant. Each task is designed to benefit a specific target: Spouse, Self, Kids, House, or Work. 
Tasks should be actionable immediately, match the time of day, and fit the participants' likely schedule.

===== GENERAL RULES =====
- Output in structured JSON: [{"target": "...", "description": "...", "type": "...", "difficulty": X, "duration": Y, "ID": Z}]
- ID is a unique identifier for the task, and the output should match the input ID.
- Some tasks include a base_idea. This idea should be incorporated in the task, and modified to fit the requested difficulty. Do not include the base_idea in the description.
- Duration is in minutes; Difficulty is 1–10
- Tasks are not related; only one will be chosen at a time
- Type is for categorization; Task or Reward
- No vague choices or either/or options
- Do not mention candles, safewords, or working around kids
- All adults are happy participants, don't need to be reminded about safewords or their ability to stop or say no.
- Tasks should not make commitments to rewards, punishments, or actions outside the stated task time.
- Tasks are scoped to fit within the allotted duration. Mention of times in the description should be avoided.

===== DIFFICULTY & LENGTH FOR TASKS =====
- 1–3: 1–5 minutes
- 4–6: 5–15 minutes
- 7–9: 15–30 minutes
- 10: 30+ minutes

===== DIFFICULTY & LENGTH FOR REWARDS =====
Rewards should be 10 minutes, The difficulty should correspond to the effort of the task. 
Rewards can be a single session (ie a single 10 minute task) or a spread throughtout the day (ie 5 one minute tasks).
The base idea is the foundation of a difficult 5 reward. Lower difficulty can be easier or require less activities, while higher difficulty should be harder.

===== TARGET PROFILES =====
**Ian** – Likes flirty, erotic, playful attention. Enjoys teasing, bold contact, being dominated, edging, and wagers (including bad odds if reward is good). 
Loves gambling challenges for erotic or light kink rewards. Enjoys loss of control and mild degradation from Karleigh. Appreciates playful flashing, nudity, oral, clothing removal, and body display from Karleigh. 

**Karleigh** – Enjoys cozy, pampering, and feeling appreciated. Prefers low-pressure sensuality, but boldness is fine as a higher difficulty challenge. 
Likes service, affection, spa-like moments, and thoughtful gestures. Likes tying/restraining Ian, dressing nicely for work/fun, and winning competitions.
Does not like baths.

**Kids** – Love imaginative, interactive, and goal-oriented play. Respond to pretend play, games, and short creative missions.

**House** – Needs clear, actionable tasks with visible improvement (cleaning, organizing, small DIY).

**Work** – Needs focused, structured tasks to support progress and momentum.

"""
        self.TARGETS = {
    "Ian": {
        "Self": """
- Focus on personal goals: jogging, listening to music, drinking more tea, exercising, and increasing steps.
- Can include small self-care challenges, creative projects, or skill practice.
""",
        "Spouse": """
- Focus on cozy, cared-for, and appreciated feelings.
- Include service, affection, thoughtful gestures, light pampering.
- Low-pressure sensual touch is welcome.
- Karleigh enjoys opportunities to dress up, and win small competitions.
- Ian shouldn't pick out Karleigh's outfits, but can comment or compliment.
- Ian should not use a "sexy" voice.
""",
        "Kids": """
- Playful, interactive, and imaginative.
- Clear goals, short duration.
- Pretend play, silly competitions, or quickcreative challenges.
""",
        "House": """
- Clear, actionable chores or improvements.

- Visible progress by the end of the task.
- Can include ongoing DIY project work.
""",
        "Work": """
- Manages household as Work
"""
    },
    "Karleigh": {
        "Self": """
- Focus on personal goals: winning small challenges, dressing nicely for work/fun, relaxing, exercising, and light self-pampering.
""",
        "Spouse": """
- Flirty, playful, erotic tone.
- Teasing, bold contact, domination, edging, and wagers are encouraged.
- Ian likes mild degradation, loss of control, and wager on orgasm denial and other erotic tasks and light kinks.
- Ian enjoys when Karleigh shows off her body — from booty shorts at home, to hidden lingerie under a dress, and the playful chance exposure of skirts.
- Karleigh enjoys opportunities to tie/restrain Ian, dress up, and win small competitions.
- Lower difficulty: playful erotic contact (flashing, touching) without pressure to escalate.
- Medium difficulty (4+): Should include foreplay-style activities.
- High difficulty (7+): Should include gambles (2 minutes to cum on my chest or nothing, no touching gets oral, resist cumming for 10 minutes or ....)
- Difficulty 9+: should include climax of Ian or Karleigh or intentional denial.
""",
        "Kids": """
- Interactive and creative play with clear objectives.
- Pretend scenarios, small games, or silly competitions.
""",
        "House": """
- Focus on maintaining her bedroom space, cleaning/organizing closet, nightstand, makeup, and bathroom.
- Willing to do small additional chores as needed.
""",
        "Work": """
- Focused, structured work blocks.
- Progress on ongoing projects.
- Remove small blockers to keep momentum.
- Remove Clutter in physical(desk, notebooks, etc) and digital(lists, notes, emails, etc) spaces.
"""
    }
}

        self.SCHEDULE = """
Monday to Friday are work and School Days
- Karleigh - Wakes up at 6AM, Leaves for Office Work at 7AM, Returns at 3-6PM. Usually works from home Monday and Friday.
- Ian - Wakes up at 7AM, Stay at home parent, Manages the kids.
- Kids - Wakes up at 7:30AM, Leaves for school at 8:20AM, Returns at 3:30PM.
Saturday is a family activity until 5PM. Then date night for Ian and Karleigh.
Sunday is a more relaxed family day.
        """
        self.EXAMPLES = {   
        "karleigh": {
            1: ["Bring her tea and straighten the blanket on the couch.",
                "Tidy her bedside and leave a little note on her nightstand."],
            2: ["Set the couch with a show queued up and a snack ready.",
                "Tidy her workspace and place a pen where she can see it."],
            3: ["Give her a 5-minute hand/foot massage while chatting softly.",
                "Write her a short note reminding her she's loved and leave it under her pillow."],
            4: ["Clean a space she uses often and don’t mention it.",
                "Send her a validating message about how much you appreciate her style and strength."],
            5: ["Offer her a slow, 15-minute back massage with no expectations.",
                "Create a quiet spot for her and play a playlist you made just for her mood."],
            6: ["Ask her “what would make today feel better?” and do it.",
                "Set up a cozy zone with tea, show, and a love note."],
            7: ["Reset the entire bedroom and invite her in for a quiet surprise cuddle.",
                "Give her a slow full-body massage with no agenda."],
            8: ["Write her a short love letter and read it aloud while massaging her shoulders.",
                "Prepare a gentle pamper scene with lotion, music, and whispered affirmations."],
            9: ["Set up a cozy spot with music. Give a slow massage—shoulders, back, hands, feet—tell her things you love. End with a small gift.",
                "Give her a guided pampering: massage, soft affirmations, and serve her a snack or drink."],
            10: ["Create a full-service pamper night: clean space, candle-free lighting, massage, and small thoughtful gift.",
                "Give her full attention, including massage, cuddles, service, and appreciation speech."]
        },
        "ian": {
            1: ["Send him a flirty emoji and give a quick kiss on the neck.",
                "Walk by and give him a butt grab or whisper something suggestive."],
            2: ["Leave a note that teases something fun later.",
                "Flash a bit of skin when he's not expecting it. — no words"],
            3: ["Let him watch you slowly dress, no commentary, just presence.",
                "Gently run your hands under his clothes while cuddling."],
            4: ["Grind briefly in his lap, then walk away smiling.",
                "Give him a short, focused massage with flirty commentary."],
            5: ["Pull out his cock, then do a slow stretch or pose in front of him. If he keeps his hands off, he earns a kiss",
                "Tell him he has 5 minutes to cum on your chest — no teasing, just focus and finish. Your terms"],
            6: ["Send a flirty pic with a challenge: if he completes it in time, reward him with more.",
                "Flip up your skirt, sit on his face, and scroll your phone. If he distracts you too much, smack/squeeze his junk and tell him to behave."],
            7: ["Lead a 10-minute teasing session where you're in control the whole time.",
                "Tie his hands loosely and kiss him everywhere but where he wants."],
            8: ["Start a seduction ritual — undress him, tease him, get yourself off, then leave him wanting more.",
                "Give him 20 minutes of oral but stop short of finishing — with a smirk."],
            9: ["Blindfold him and spend time exploring and teasing him slowly.",
                "Pick outfits for both of you — something that makes you feel hot. Tell him to stay completely silent, then use him to get yourself off."],
            10: ["Seduce him your way — slow, teasing, and in full control. When he's close, flip a coin. Only the winner gets to finish.",
                "Design a themed scene with music, costume, and slow irresistible touch until he begs to finish himself."]
        },
        "kids": {
            1: ["Pretend you're a dragon sneaking snacks with them.",
                "Do a 3-minute silly dance contest with superhero poses."],
            2: ["Let them give you a new superhero name and play it for 5 minutes.",
                "Create a quick quest to find 3 magical items around the house."],
            3: ["Draw your own comic panels together for 10 minutes.",
                "Let them 'train' you in fairy combat in the living room."],
            4: ["Build a mini obstacle course and run through it twice with them.",
                "Write and perform a 2-character skit they direct."],
            5: ["Act out a mini mission to “save the living room kingdom.”",
                "Make a scroll, map, or invitation to a pretend event."],
            6: ["aaCreate a scavenger hunt they solve by answering silly riddles.",
                "Play ‘Fairy School’ for 20 minutes where they are the teacher."],
            7: ["Help them write a 3-part fairy tale and act it out.",
                "Do a 30-minute adventure game where you’re the monster they defeat."],
            8: ["Host a living room 'Talent Show' with music, costumes, and cheering.",
                "Design and complete a superhero training course with checkpoints."],
            9: ["Do a 3-room pretend quest with roles, battles, and a final treasure.",
                "Help them film a short action or comedy sketch"],
            10: ["Spend time co-creating a fantasy world, map, and rules together.",
                "Film and act out a full 3-scene superhero story they invent."]
        },
        "house": {
            1: ["Wipe down a surface that gets messy fast.",
                "Pick up a pile that’s been sitting around."],
            2: ["Unload or reload the dishwasher.",
                "Sweep or vacuum a small area."],
            3: ["Vacuum a shared room and reset the furniture.",
                "Refill something (toilet paper, paper towels, soap)."],
            4: ["Wipe down bathroom surfaces and restock toilet paper/towels.",
                "Declutter and dust a side table or bookshelf."],
            5: ["Clean the kitchen sink and one appliance (microwave, fridge handle).",
                "Clean bathroom mirror and faucet to sparkle."],
            6: ["Do a deep clean of one bathroom — including floor and toilet.",
                "Clear and reorganize the dining table and nearby surfaces."],
            7: ["Do a 30-minute reset of any lived-in room, including cleaning and aesthetics.",
                "Wash, dry, and fold one load of shared laundry completely."],
            8: ["Declutter a shared closet or drawer that’s been neglected.",
                "Organize and clean the fridge (sort expired items too)."],
            9: ["Fix, patch, or polish something that’s been bugging you both.",
                "Clean a forgotten area (under couch, fan blades, cords)."],
            10: ["Deep clean and beautify a full shared space, including decor, surfaces, and hidden messes.",
                "Do a full bathroom deep clean including grout/scrub."]
        },
        "work": {
            1: ["Review your task list and star 2 must-do items.",
                "Sort your desktop or workspace for 3 minutes."],
            2: ["Write a to-do list for the next 2 hours of work.",
                "Move any open browser tabs into categories or close unused ones."],
            3: ["Reply to or archive 5 old emails.",
                "Organize one project folder or shared drive."],
            4: ["Draft or update a key document for 10 minutes.",
                "Reorganize a doc or folder you use daily."],
            5: ["Finish a light admin task you've been avoiding.",
                "Start and make measurable progress on a creative task."],
            6: ["Write and polish a deliverable or client-facing message.",
                "Write and send something that's been looming emotionally."],
            7: ["Make strategic progress on a hard-to-start task.",
                "Create a full brief or outline for an upcoming deliverable."],
            8: ["Complete a deep work session on one hard problem (30+ minutes).",
                "Make good progress on something where you've been stuck."],
            9: ["Finish a time-intensive priority and send it off with a clean wrap-up message.",
                "Audit a part of your system for inefficiencies outline the cleanup"],
            10: ["Take a public or emotional leap in your work life (ask, apply, propose).",
                "Clear or Organize your backlog and plan to a clean slate."]
        },
        "self": {
        1: ["Take 5 deep, slow breaths.",
            "Drink a full glass of water and stretch your arms overhead."],
        2: ["Step away from your screen and look out a window for 2 minutes.",
            "Listen to one of your favorite songs from start to finish."],
        3: ["Go for a brisk 5-minute walk (indoors or outdoors).",
            "Write down three things you're grateful for right now."],
        4: ["Tidy your immediate personal space for 10 minutes.",
            "Do a 10-minute guided meditation or breathing exercise."],
        5: ["Spend 15 minutes reading a book or article for pleasure.",
            "Do 15 minutes of light exercise or a full-body stretching routine."],
        6: ["Spend 20 minutes working on a hobby you enjoy.",
            "Call or send a thoughtful message to a friend or family member."],
        7: ["Journal freely for 20 minutes about your thoughts and feelings.",
            "Plan a healthy meal and prepare one component of it."],
        8: ["Engage in 25 minutes of focused learning for a personal interest (e.g., language app, tutorial).",
            "Do a 25-minute workout that makes you break a sweat."],
        9: ["Tackle a personal admin task you've been avoiding for 30 minutes (e.g., schedule appointment, sort mail).",
            "Do a 'brain dump'—write down everything on your mind—and then organize it."],
        10: ["Create a detailed 30-minute plan for a personal goal (e.g., map out a fitness plan, outline a creative project).",
            "Do a 30-minute deep-cleaning or decluttering of one small area (e.g., a drawer, a bookshelf)."]
        }
        }

        self.REWARD_PROMPT = f"""
            You are generating special reward options.
            These are intimate/playful activities that the spouse will do for the participant as a treat the participant earned.

            OUTPUT FORMAT
            - "reward" must be less than 20 words.

            THEMES
            - For each item, you will be given two themes. Rewards should be based on and include both themes.
            - Some Themes may include examples, use them to help you understand the theme, but you are encouraged to make up your own specific reward.
            - You may be asked to make up a theme, keep it consitent with other themes, but make it unique and something the participant will enjoy.

            STRICT RULES (VERY IMPORTANT)
            - Be SPECIFIC: choose concrete details (e.g., “neck kiss,” “living room,” “lingerie”) rather than placeholders like “preferred body part,” “chosen location,” “favorite outfit.”
            - No variables or brackets: do NOT write "body part", (X), <choice>, “pick,” “select,” or “TBD.”
            - No sequencing or chaining: avoid “then,” “followed by,” “if/else,” “first/next,” or step lists. Each reward is ONE self-contained concept.
            - No “this-then-that” constructions (e.g., “massage then cuddle then…”). Choose the single most important idea.
            
            REWARDS THAT INVOLVE SEXY TIMES
            - Be specific if a person is supposed to get off or cum.
            - Be specific if a person is not allowed to get off or cum.
            - Be specific if a person is supposed to wager or gamble to get off or cum.
            - If a reward is intimate but not sexual, you do not need to mention orgasms, getting off, or cumming.

            REWARDS THAT INVOLVE WAGERS OR GAMBLING
            - Be specific on what you are wagering or gambling on
            - Be specific on the win or loss prize of the wager
            - Rewards about winning should have a competition and prize or penalty

            CONCRETENESS HELPERS
            - If a body part is implied, pick ONE specific option (neck, tits, hands, chest, butt, inner thighs, etc).
            - If a location is implied, pick ONE specific, non-public space (bedroom, shower, couch, living room, etc).
            - If clothing/costume is implied, pick ONE simple option/concept (lingerie, workout clothes, comfy sweater, dress, etc).
            - Dont't mention specific times, those will be figured out seperately.


            Return only the JSON list.
            """
        self.REWARD_THEMES = {   
        "karleigh": (
            ("Ian Makes Art About his Love for Karleigh", ("Poem", "Letter", "Drawing")),
            ("Karleigh Gets Off", ("Happy Ending", "Toy", "Handjob")),
            ("Receive a Gift", ("Chocolate", "Something Beautiful", "Something Sexy")),
            ("Scalp Massage", ("Head Massage", "Oil Brushed")),
            ("Manicure/Pedicure", ("Soak and Scrub", "Paint", "Hand Massage", "Trim and Lotion")),
            ("Mini Spa Treatment", ("Paraffin Wax", "Exfoliating Scrub", "Facial", "Aromatic Foot Soak")),
            ("Massage", ("Back Massage", "Foot Massage", "Full Body Massage", "Body Rollers")), 
            ("Be Read to", ("Short Story", "Poem", "Article")), 
            ("Watch Something", ("Comic", "Music", "Show")),
            ('Karleigh Wins', ("Easy Competition", "Silly Game", "Trivia")),
        ),
        "ian": (
            ("Karleigh Shows Off", ("Flash", "Strip", "Sexy Outfit")), 
            ("Outside the Bedroom", ("Living Room", "Chair", "Park")), 
            ("Ian's Restrained", ("Tied", "Blindfold", "Face Sitting")), 
            ("Suprise Start", ("Karleigh lets Ian know a task is ready, Ian suprises her when its the start time")),
            ("Finish on a Karleigh's Specific Body Part", ("Tits", "Ass", "Face", "Thighs")),
            ("Porn", ()), 
            ("5 Separate Small Moments", ("5 Edges", "5 Flashes Throughout the Day", "5 1min Handjobs", "5 Pussy Tastes")), 
            ("Karleigh Wears Slightly Too Little for the Setting", ("Skirt", "Slutty Underwear", "No Underwear")), 
            ("Orgasm Wager", ("15 Minutes to Cum or Nothing", "No Touching Gets Oral", "Resist Cumming for 10 Minutes or Takes Out the Trash")), 
        )

        }