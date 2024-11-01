import random
import numpy as np
import warnings

# In this class the models of entities are defined including their functions (e.g. bidding behavior of agents)

class Ticket:
    def __init__(self, id, params, previous_state=None):
        self.id = id
        self.assigned = False
        self.holder_id = None
        self.assigned_slot = None
        self.assigned_epoch = None
        self.price_paid = 0 
        self.redeemed = False
        self.expiry_slot = None
        # Setup logic for expiring tickets (if not None).
        if params['expiry_period'] is not None:
            if self.id < params['max_tickets']: # Check if initalization phase
                self.expiry_slot = (id + params['expiry_period']) # Expiry is linear based on ticket id, to avoid invalidation of all tickets after max_tickets slots
            else:
                self.expiry_slot = (previous_state['slot'] + params['expiry_period'])

# Define the TicketHolders as Agents
class TicketHolderAgent:
    def __init__(self, id, params):
        self.id = id
        num_holders = params['number_of_ticket_holders']
        if self.id <= (num_holders * 0.2):
            self.type = 'top'
            self.available_funds = random.uniform(400, 1000)
            self.MEV_capture_rate = random.uniform(0.85, 0.95)
        elif self.id > (num_holders * 0.2) and self.id <= (num_holders * 0.6):
            self.type = 'middle'
            self.available_funds = random.uniform(300, 700)
            self.MEV_capture_rate = random.uniform(0.75, 0.85)
        elif self.id > (num_holders * 0.6):
            self.type = 'tail'
            self.available_funds = random.uniform(200, 500)
            self.MEV_capture_rate = random.uniform(0.6, 0.75)
        self.aggressiveness = np.random.normal(0.15, 0.02) # np.random.normal(mean, std_dev) # random.uniform(0.01, 0.3) # to be adjusted later
        self.vola_spec_factor = np.random.normal(1, 0.5) # Random distribution of builder volatility specialization
        if self.vola_spec_factor <=  0: self.vola_spec_factor = 0.1
        self.earnings = 0
        self.costs = 0
        self.purchase_value_of_unredeemed_tickets = 0
        self.won_slots = []
        self.discount_factor = 1 # Currently usually set to 1, see research report for details. Reflects the inter-slot dicount factor

    # needs to be adjusted if init function changes
    # Bidder are aware that tickets are expiring. In case the ticket is expiring the value is discounted.
    def decide_bid_first_price(self, params): 
        """Calculate bid based on intrinsic valuation, funds, and aggressiveness."""
        
        # In this case the agents staticly bid evenly distributed between 10 and 50
        if params['agent_bidding_strategy'] == 'random_evenly_10_50':
            max_bid = random.uniform(10, 50) * (1 - self.aggressiveness)

        # In this scenario the agents have observed the historical distribution of MEV values and estimate the average
        elif params['agent_bidding_strategy'] == 'naive_hist_obs_of_dist':
            max_bid = params['MEV_scale'] * (1 - self.aggressiveness) #params['MEV_scale'] gives the mean & SD for the distribution.

        # In this scenario the agents have observed the historical distribution of MEV values and estimate the average and are aware of their own ability to capture MEV
        elif params['agent_bidding_strategy'] == 'hist_obs_of_dist':
            max_bid = params['MEV_scale'] * self.MEV_capture_rate * (1 - self.aggressiveness)

        # In this scenario the agents have observed historical distirbution, estimate aware of their ability and the optimal research-based heuristic for FPA
        elif params['agent_bidding_strategy'] == 'optimal_heuristic_bidding':
            max_bid = params['MEV_scale'] * self.MEV_capture_rate * (1 - self.aggressiveness) * ((params['number_of_ticket_holders']-1)/params['number_of_ticket_holders'])
                    
        # Conservative bidding of ticket holder with the minimum observed value
        elif params['agent_bidding_strategy'] == 'conservative_min':
            max_bid = min(np.random.exponential(params['MEV_scale']) for _ in range(10))

        # Calculate the discount factor for expring tickets (see documentation for details)
        # Note that this implementation implicitly assumes that all tickets are always sold. For simplicity reasons we make this assumption as this is usually the case given any TH still has funds.
        if params['expiry_period'] is not None:
            discount_factor_exp_tickets = 1 - (1 - params['slots_per_epoch']/params['max_tickets'])**(params['expiry_period']/params['slots_per_epoch'])
            if 0 < discount_factor_exp_tickets <= 1:
                max_bid = max_bid * discount_factor_exp_tickets
            else:
                print(f"Error in calculating the discount factor in the bid calculation resulting in: {discount_factor_exp_tickets}")
        
        #print(f"Agent {self.id} wants to bid {max_bid}. Available funds {self.available_funds}") #Debug Print

        return min(max_bid, self.available_funds)

    ## Currently same bidding strategy as first price as intrinsic valuation calculation shall be the same
    def decide_bid_second_price(self, params, ticket_for_sale=None, current_slot=None, vola_this_slot=None, previous_state = None):
        
        # In this case the agents staticly bid evenly distributed between 10 and 50
        if params['agent_bidding_strategy'] == 'random_evenly_10_50':
            max_bid = random.uniform(10, 50) * (1 - self.aggressiveness)

        # In this scenario the agents have observed the historical distribution of MEV values and estimate the average
        elif params['agent_bidding_strategy'] == 'naive_hist_obs_of_dist':
            max_bid = params['MEV_scale'] * (1 - self.aggressiveness) #params['MEV_scale'] gives the mean & SD for the distribution.

        # In this scenario the agents have observed the historical distribution of MEV values and estimate the average and are aware of their own ability to capture MEV
        elif params['agent_bidding_strategy'] == 'hist_obs_of_dist':
            max_bid = params['MEV_scale'] * self.MEV_capture_rate * (1 - self.aggressiveness)
        
        # Conservative bidding of ticket holder with the minimum observed value
        elif params['agent_bidding_strategy'] == 'conservative_min':
            max_bid = min(np.random.exponential(params['MEV_scale']) for _ in range(10)) 

        elif params['agent_bidding_strategy'] == 'optimal_heuristic_bidding' and params['secondary_market'] == True:
            max_bid = params['MEV_scale'] * self.MEV_capture_rate * (1 - self.aggressiveness)

        # Pricing for JIT Slot auctions. Assumptions change, that MEV & Vola this slot is known 
        if params['max_tickets'] == 1:
            vola_this_slot = previous_state['Volatility_per_slot']
            adjustment_factor_vola = 1+(vola_this_slot - params['expected_vola'])*self.vola_spec_factor
            max_bid = previous_state['MEV_per_slot'] * self.MEV_capture_rate * (1 - self.aggressiveness) * adjustment_factor_vola

        # Calculate the discount factor for expring tickets (see documentation for details)
        # Note that this implementation implicitly assumes that all tickets are always sold. For simplicity reasons we make this assumption as this is usually the case given any TH still has funds.
        if params['expiry_period'] is not None and ticket_for_sale is None:
            discount_factor_exp_tickets = 1 - (1 - params['slots_per_epoch']/params['max_tickets'])**(params['expiry_period']/params['slots_per_epoch'])
            if 0 < discount_factor_exp_tickets < 1:
                max_bid = max_bid * discount_factor_exp_tickets
            else:
                warnings.warn(f"Error in calculating the discount factor in the bid calculation resulting in: {discount_factor_exp_tickets}", UserWarning)
      
        # Pricing For Secondary Market Transactions
        if ticket_for_sale is not None:
            # Check if the ticket for this slot is sold
            if ticket_for_sale.assigned_slot is None or ticket_for_sale.assigned_slot != current_slot:
                # Price Adjustment Logic for Expiring Tickets
                # Check if ticket is expiring & not already allocated (if allocated no risk discount needed)
                if ticket_for_sale.expiry_slot is not None and ticket_for_sale.assigned_slot is None:
                        remaining_time = ticket_for_sale.expiry_slot - current_slot
                        # Potential improvement: Further discount by checking how many future slots are already allocated
                        # therefore iterate over all tickets, collect allocated slots and divide "free" slots by outstanding tickets
                        print(f"Ticket: {ticket_for_sale.id} has {remaining_time} slots to be allocated.")
                        discount_factor_exp_tickets_sm = 1 - (1 - params['slots_per_epoch']/params['max_tickets'])**(remaining_time/params['slots_per_epoch'])
                        if 0 < discount_factor_exp_tickets_sm <= 1:
                            max_bid = max_bid * discount_factor_exp_tickets_sm
                        elif discount_factor_exp_tickets_sm == 0:
                            max_bid = 0 # The ticket is getting invalided in this slot (later) so it is worth nothing
                        else:
                            warnings.warn(f"Error in calculating the discount factor in the bid calculation resulting in: {discount_factor_exp_tickets_sm}", UserWarning)
                
                # Price Adjustment Logic for Assigned Slot 
                if ticket_for_sale.assigned_slot is not None:
                    remaining_time = ticket_for_sale.assigned_slot - current_slot
                    max_bid = max_bid * ((self.discount_factor) ** remaining_time) # Potentially to be adjusted later based on definition of discount factor                    
            # Price Evaluation Logic for Current Slot Ticket where Volatility is known   
            else:
                adjustment_factor_vola = 1+(vola_this_slot - params['expected_vola'])*self.vola_spec_factor
                max_bid = max_bid * adjustment_factor_vola

        return min(max_bid, self.available_funds)

    
    def decide_EIP_1559_ticket(self, ticket_price, params):

        # if params['agent_bidding_strategy'] == 'hist_obs_of_dist': # to be implemented later / extract intrinsic valuation logic?
        if params['expiry_period'] is not None:
            discount_factor_exp_tickets = 1 - (1 - params['slots_per_epoch']/params['max_tickets'])**(params['expiry_period']/params['slots_per_epoch'])
        else:
            discount_factor_exp_tickets = 1


        if (params['MEV_scale'] * self.MEV_capture_rate * (1 - self.aggressiveness) * discount_factor_exp_tickets) > ticket_price:
            willingness_to_pay = params['MEV_scale'] * self.MEV_capture_rate * (1 - self.aggressiveness) * discount_factor_exp_tickets
            print(f"Agent {self.id} has a willingness to pay of: {willingness_to_pay}")
            return True
        else:
            return False

    def decide_AMM_ticket(self, ticket_price, params):

        # if params['agent_bidding_strategy'] == 'hist_obs_of_dist': # to be implemented later / extract intrinsic valuation logic?
        if params['expiry_period'] is not None:
            discount_factor_exp_tickets = 1 - (1 - params['slots_per_epoch']/params['max_tickets'])**(params['expiry_period']/params['slots_per_epoch'])
        else:
            discount_factor_exp_tickets = 1

        if (params['MEV_scale'] * self.MEV_capture_rate * (1 - self.aggressiveness) * discount_factor_exp_tickets) > ticket_price:
            willingness_to_pay = params['MEV_scale'] * self.MEV_capture_rate * (1 - self.aggressiveness) * discount_factor_exp_tickets
            print(f"Agent {self.id} has a willingness to pay of: {willingness_to_pay}")
            return True
        else:
            return False
    
    def holder_decide_AMM_sell(self, tickets, ticket_price, params):
        for ticket in tickets:
            if ticket.holder_id == self.id:
                return (params['MEV_scale'] * self.MEV_capture_rate * (1 - self.aggressiveness)) < (ticket_price * (1 - params['reimbursement_factor']))
        return False