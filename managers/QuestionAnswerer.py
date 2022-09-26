from time import sleep
import asyncio

class QuestionAnswerer(object):
    def __init__(self, firebase_manager, ai_manager):
        self.firebase_manager = firebase_manager
        self.ai_manager = ai_manager

    def make_prompt(self, context, question):
        prompt = f'{context} mnli {question}'
        return prompt

    async def answer_question(self, puzzle_id, question):
        puzzle_data = await self.firebase_manager.puzzle_data(puzzle_id)
        context = puzzle_data['context']
        prompt = self.make_prompt(context, question)
        model_reply = await self.ai_manager.complete_prompt(prompt)
        if model_reply == '0':
            return 'Yes'
        elif model_reply == '1':
            return 'Irrelevant'
        elif model_reply == '2':
            return 'No'
        else:
            return 'Sorry, something went wrong :('

    async def check_single_solution_part(self, input_str):
        print('input_str:', input_str)
        completion = await self.ai_manager.complete_prompt(input_str)
        print('completion:', completion)
        return completion == '0'

    async def bool_from_json(self, guess, json_dict, check_str):
        if len(json_dict) != 1:
            raise Exception('Dictionary should have exactly one key, AND or OR')
        operator = list(json_dict.keys())[0]
        
        async def check_true(element):
            if isinstance(element, str):
                is_true = await check_str(f"{guess} mnli {element}")
                return is_true
            elif isinstance(element, dict):
                is_true = await self.bool_from_json(guess, element, check_str)
                return is_true
            else:
                raise Exception('Invalid element type')
        
        bools = await asyncio.gather(*[check_true(element) 
                                    for element in json_dict[operator]])
        
        print('bool_from_json:', bools)
        res = None
        if operator == 'AND':
            res = all(bools)
        elif operator == 'OR':
            res = any(bools)
        else:
            raise Exception('Invalid operator')
        return res

    async def check_solution(self, puzzle_id, guess):
        puzzle_data = await self.firebase_manager.puzzle_data(puzzle_id)
        checks_json = puzzle_data['checks']
        all_correct = await self.bool_from_json(guess, checks_json, self.check_single_solution_part)
        return all_correct

    