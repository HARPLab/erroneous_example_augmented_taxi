# Python imports.
from __future__ import print_function
from collections import defaultdict
import sys

# Other imports.
from simple_rl.planning.ValueIterationClass import ValueIteration
from simple_rl.mdp import State
from simple_rl.mdp import MDPDistribution
from simple_rl.abstraction.state_abs import indicator_funcs as ind_funcs
from simple_rl.abstraction.state_abs.StateAbstractionClass import StateAbstraction

def merge_state_abs(list_of_sa, track_act_opt_pr=False):
    '''
    Args:
        list_of_sa (list of StateAbstraction)

    Returns:
        (StateAbstraction)
    '''
    merged = list_of_sa[0]

    for sa in list_of_sa[1:]:
        merged = merged + sa

    return merged

def make_sa(mdp, indic_func=ind_funcs._q_eps_approx_indicator, state_class=State, epsilon=0.0, save=False, track_act_opt_pr=False):
    '''
    Args:
        mdp (MDP)
        state_class (Class)
        epsilon (float)

    Summary:
        Creates and saves a state abstraction.
    '''
    print("  Making state abstraction... ")
    q_equiv_sa = StateAbstraction(phi={}, track_act_opt_pr=track_act_opt_pr)
    if isinstance(mdp, MDPDistribution):
        q_equiv_sa = make_multitask_sa(mdp, state_class=state_class, indic_func=indic_func, epsilon=epsilon, track_act_opt_pr=track_act_opt_pr)
    else:
        q_equiv_sa = make_singletask_sa(mdp, state_class=state_class, indic_func=indic_func, epsilon=epsilon, track_act_opt_pr=track_act_opt_pr)

    if save:
        save_sa(q_equiv_sa, str(mdp) + ".p")

    return q_equiv_sa

def make_multitask_sa(mdp_distr, state_class=State, indic_func=ind_funcs._q_eps_approx_indicator, epsilon=0.0, aa_single_act=True, track_act_opt_pr=False):
    '''
    Args:
        mdp_distr (MDPDistribution)
        state_class (Class)
        indicator_func (S x S --> {0,1})
        epsilon (float)
        aa_single_act (bool): If we should track optimal actions.

    Returns:
        (StateAbstraction)
    '''
    sa_list = []
    for mdp in mdp_distr.get_mdps():
        sa = make_singletask_sa(mdp, indic_func, state_class, epsilon, aa_single_act=aa_single_act, prob_of_mdp=mdp_distr.get_prob_of_mdp(mdp), track_act_opt_pr=track_act_opt_pr)
        sa_list += [sa]

    multitask_sa = merge_state_abs(sa_list, track_act_opt_pr=track_act_opt_pr)

    return multitask_sa

def make_singletask_sa(mdp, indic_func, state_class, epsilon=0.0, aa_single_act=False, prob_of_mdp=1.0, track_act_opt_pr=False):
    '''
    Args:
        mdp (MDP)
        indic_func (S x S --> {0,1})
        state_class (Class)
        epsilon (float)

    Returns:
        (StateAbstraction)
    '''

    print("\tRunning VI...",)
    sys.stdout.flush()
    # Run VI
    if isinstance(mdp, MDPDistribution):
        mdp = mdp.sample()

    vi = ValueIteration(mdp)
    iters, val = vi.run_vi()
    print(" done.")

    print("\tMaking state abstraction...",)
    sys.stdout.flush()
    sa = StateAbstraction(phi={}, state_class=state_class, track_act_opt_pr=track_act_opt_pr)
    clusters = defaultdict(list)
    num_states = len(vi.get_states())

    actions = mdp.get_actions()
    # Find state pairs that satisfy the condition.
    for i, state_x in enumerate(vi.get_states()):
        sys.stdout.flush()
        clusters[state_x] = [state_x]

        for state_y in vi.get_states()[i:]:
            if not (state_x == state_y) and indic_func(state_x, state_y, vi, actions, epsilon=epsilon):
                clusters[state_x].append(state_y)
                clusters[state_y].append(state_x)

    print("making clusters...",)
    sys.stdout.flush()
    
    # Build SA.
    for i, state in enumerate(clusters.keys()):
        new_cluster = clusters[state]
        sa.make_cluster(new_cluster)

        # Destroy old so we don't double up.
        for s in clusters[state]:
            if s in clusters.keys():
                clusters.pop(s)
    
    if aa_single_act:
        # Put all optimal actions in a set associated with the ground state.
        for ground_s in sa.get_ground_states():
            a_star_set = set(vi.get_max_q_actions(ground_s))
            sa.set_actions_state_opt_dict(ground_s, a_star_set, prob_of_mdp)

    print(" done.")
    print("\tGround States:", num_states)
    print("\tAbstract:", sa.get_num_abstr_states())
    print()

    return sa

def visualize_state_abstr_grid(grid_mdp, state_abstr, scr_width=720, scr_height=720):
    '''
    Args:
        grid_mdp (GridWorldMDP)
        state_abstr (StateAbstraction)

    Summary:
        Visualizes the state abstraction.
    '''
    import pygame
    from simple_rl.utils import mdp_visualizer

    pygame.init()
    title_font = pygame.font.SysFont("CMU Serif", 32)
    small_font = pygame.font.SysFont("CMU Serif", 22)

    if isinstance(grid_mdp, MDPDistribution):
        goal_locs = set([])
        for m in grid_mdp.get_all_mdps():
            for g in m.get_goal_locs():
                goal_locs.add(g)
        grid_mdp = grid_mdp.sample()
    else:
        goal_locs = grid_mdp.get_goal_locs()

    # Pygame init.  
    screen = pygame.display.set_mode((scr_width, scr_height))
    pygame.init()
    screen.fill((255, 255, 255))
    pygame.display.update()
    mdp_visualizer._draw_title_text(grid_mdp, screen)

    # Prep some dimensions to make drawing easier.
    scr_width, scr_height = screen.get_width(), screen.get_height()
    width_buffer = scr_width / 10.0
    height_buffer = 30 + (scr_height / 10.0) # Add 30 for title.
    cell_width = (scr_width - width_buffer * 2) / grid_mdp.width
    cell_height = (scr_height - height_buffer * 2) / grid_mdp.height
    font_size = int(min(cell_width, cell_height) / 4.0)
    reg_font = pygame.font.SysFont("CMU Serif", font_size)
    cc_font = pygame.font.SysFont("Courier", font_size*2 + 2)

    # Setup states to compute abstr states later.
    state_dict = defaultdict(lambda : defaultdict(bool))
    for s in state_abstr.get_ground_states():
        state_dict[s.x][s.y] = s

    # Grab colors.
    from simple_rl.utils.chart_utils import color_ls
    while state_abstr.get_num_abstr_states() > len(color_ls):
        color_ls.append((random.randint(0,255), random.randint(0,255), random.randint(0,255)))

    # For each row:
    for i in range(grid_mdp.width):
        # For each column:
        for j in range(grid_mdp.height):

            if not state_dict[i+1][grid_mdp.height - j]:
                # An unreachable state.
                continue

            # Draw the abstract state colors.
            top_left_point = width_buffer + cell_width*i, height_buffer + cell_height*j
            s = state_dict[i+1][grid_mdp.height - j]
            abs_state = state_abstr.phi(s)
            cluster_num = abs_state.data #state_abstr.get_abs_cluster_num(abs_state)
            abstr_state_color = color_ls[cluster_num % len(color_ls)]
            r = pygame.draw.rect(screen, abstr_state_color, (top_left_point[0] + 5, top_left_point[1] + 5) + (cell_width-10, cell_height-10), 0)
            r = pygame.draw.rect(screen, (46, 49, 49), top_left_point + (cell_width, cell_height), 3)

            if grid_mdp.is_wall(i+1, grid_mdp.height - j):
                # Draw the walls.
                top_left_point = width_buffer + cell_width*i + 5, height_buffer + cell_height*j + 5
                r = pygame.draw.rect(screen, (255, 255, 255), top_left_point + (cell_width-10, cell_height-10), 0)
                text = reg_font.render("(wall)", True, (46, 49, 49))
                screen.blit(text, (top_left_point[0] + 10, top_left_point[1] + 20))

            if (i+1,grid_mdp.height - j) in goal_locs:
                # Draw goal.
                circle_center = int(top_left_point[0] + cell_width/2.0), int(top_left_point[1] + cell_height/2.0)
                circler_color = (154, 195, 157)
                pygame.draw.circle(screen, circler_color, circle_center, int(min(cell_width, cell_height) / 3.0))

                # Goal text.                
                text = reg_font.render("Goal", True, (46, 49, 49))
                offset = int(min(cell_width, cell_height) / 3.0)
                goal_text_point = circle_center[0] - font_size, circle_center[1] - font_size/1.5
                screen.blit(text, goal_text_point)

    pygame.display.flip()

    raw_input("Press enter to exit: ")