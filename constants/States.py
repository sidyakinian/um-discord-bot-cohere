class States(object):
    tutorial_welcome = 'tutorial_welcome'   # Initial state after the user joins the server
    tutorial_example = 'tutorial_example'
    tutorial_iceberg = 'tutorial_iceberg'
    tutorial_first_guess = 'tutorial_first_guess'
    tutorial_possibility_tree = 'tutorial_possibility_tree'
    tutorial_irrelevant = 'tutorial_irrelevant'
    tutorial_submit = 'tutorial_submit'
    tutorial_hints = 'tutorial_hints'
    tutorial_privacy = 'tutorial_privacy'
    tutorial_now_solve = 'tutorial_now_solve'   # From this state, we move to idle

    idle = 'idle'
    playing = 'playing'