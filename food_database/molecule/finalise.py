# AUTOGENERATED! DO NOT EDIT! File to edit: ../../notebooks/09-molecule-db-finalising.ipynb.

# %% auto 0
__all__ = ['root', 'all_compounds', 'search_duplicate_food_matches', 'calculate_match_stats',
           'select_from_filtered_duplicate_matches', 'calculate_relative_content_sizes',
           'filter_low_content_unique_foods', 'select_citation_orig_food', 'select_from_orig_foods',
           'full_select_duplicate_foods', 'calculate_content_averages']

# %% ../../notebooks/09-molecule-db-finalising.ipynb 7
from pyprojroot import here
root = here()
import sys
sys.path.append(str(root))

# %% ../../notebooks/09-molecule-db-finalising.ipynb 8
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

import json

from .join import *
from ..density.food_join import *

from functools import reduce

import pickle

# %% ../../notebooks/09-molecule-db-finalising.ipynb 9
pd.options.mode.chained_assignment = None  # default='warn'

# %% ../../notebooks/09-molecule-db-finalising.ipynb 36
def search_duplicate_food_matches(ingredient, duplicate_foods):

    ingredient = ingredient[ingredient.notnull()]

    matched_duplicate_foods = duplicate_foods
    matched_idxs = matched_duplicate_foods.index
    found_match = False

    for search_col, search_word in ingredient.items():

        current_matched_idxs = matched_duplicate_foods.index[matched_duplicate_foods.apply(fuzzy_search, args=(search_word,))]

        if not current_matched_idxs.empty:
            matched_idxs = current_matched_idxs
            found_match = True
        else:
            if not search_col.startswith('name.name.nouns'):
                pass
        
        matched_duplicate_foods = matched_duplicate_foods.loc[matched_idxs]

    if not found_match: matched_idxs = []

    return matched_duplicate_foods

# %% ../../notebooks/09-molecule-db-finalising.ipynb 40
with open(f'{root}/data/globals/default_words.json', 'r') as f:
    default_words = json.load(f)['molecule']

# %% ../../notebooks/09-molecule-db-finalising.ipynb 42
def calculate_match_stats(match_string, ingredient_values):
    match_position = 99
    whole_match_count = 0
    match_count = 0
    name_word_count = 99
    default_word_count = 0
    match_words = match_string.split(' ')
    for i, match_word in enumerate(match_words):
        if any([v for v in ingredient_values if fuzzy_search(v, match_word)]):
            match_position = i
            match_count += 1
        if any([v for v in ingredient_values if v == match_word]):
            whole_match_count += 1
        if any([w for w in default_words if w == match_word]):
            default_word_count += 1
    name_word_count = len(match_words)
    name_word_count -= default_word_count
    return (
        match_position,
        whole_match_count,
        match_count, 
        name_word_count,
        default_word_count
    )

# %% ../../notebooks/09-molecule-db-finalising.ipynb 43
def select_from_filtered_duplicate_matches(ingredient, matches, return_df=False):

    # since we don't have any rubbish foods here, we can include all search terms of the ingredient
    ingredient_cols = ingredient.index[ingredient.notnull()]
    ingredient_values = ingredient[ingredient_cols].values

    matched_df = matches.to_frame('name')

    matched_df['match_position'], \
    matched_df['whole_match_count'], \
    matched_df['match_count'], \
    matched_df['name_word_count'], \
    matched_df['default_word_count'] = zip(*matched_df['name'].apply(calculate_match_stats, args=(ingredient_values,)))

    matched_df = matched_df.sort_values(
        ['match_position',
         'whole_match_count',
         'match_count',
         'default_word_count',
         'name_word_count',
         'unique_food_id'],
        ascending = [
            True,
            False,
            False,
            False,
            True,
            True
        ]
    )

    if return_df:
        return matched_df
    else:
        return matched_df.iloc[0].name if not matched_df.empty else pd.NA

# %% ../../notebooks/09-molecule-db-finalising.ipynb 49
def calculate_relative_content_sizes(citation, matched_content_df):
    matched_content_df = matched_content_df.loc[citation]
    sizes = matched_content_df.groupby('unique_food_id').size()
    total_size = sizes.sum()
    n_foods = len(sizes)
    relative_content_sizes = sizes.apply(lambda x: x/total_size*n_foods)
    return relative_content_sizes

# %% ../../notebooks/09-molecule-db-finalising.ipynb 51
def filter_low_content_unique_foods(matched_unique_foods, citation, matched_content_df):
    relative_content_sizes = calculate_relative_content_sizes(citation, matched_content_df)
    selection = relative_content_sizes[relative_content_sizes > 2]
    if not selection.empty: relative_content_sizes = selection
    relative_content_sizes = relative_content_sizes[relative_content_sizes > 0.5]
    return matched_unique_foods.loc[relative_content_sizes.index]

# %% ../../notebooks/09-molecule-db-finalising.ipynb 56
def select_citation_orig_food(matched_unique_orig_foods, ingredient, matched_content_df, return_full_index=True):

    if len(matched_unique_orig_foods) == 1: return matched_unique_orig_foods.index[0][1]
    if matched_unique_orig_foods.empty: return pd.NA
    
    citation = matched_unique_orig_foods.iloc[0].name[0]
    matched_unique_orig_foods = matched_unique_orig_foods.droplevel(0)['orig_food_common_name']
    
    matched_unique_orig_foods = filter_low_content_unique_foods(matched_unique_orig_foods, citation, matched_content_df)

    if len(matched_unique_orig_foods) == 1: return matched_unique_orig_foods.index[0]

    searched_unique_local_foods = search_duplicate_food_matches(ingredient, matched_unique_orig_foods)
    selected_food = select_from_filtered_duplicate_matches(ingredient, searched_unique_local_foods)
    
    return selected_food

# %% ../../notebooks/09-molecule-db-finalising.ipynb 60
def select_from_orig_foods(matched_unique_orig_foods, ingredient, matched_content_df, return_full_index=True):
    return matched_unique_orig_foods.groupby('citation', observed=True).apply(select_citation_orig_food, (ingredient), (matched_content_df), (return_full_index))

# %% ../../notebooks/09-molecule-db-finalising.ipynb 63
def full_select_duplicate_foods(ingredient, unique_orig_foods, content_df):

    food_id = ingredient['food_id']
    ingredient = ingredient.drop('food_id')
    if pd.isnull(food_id): return pd.NA
    if food_id not in unique_orig_foods.index.get_level_values(0): return pd.NA

    matched_unique_orig_foods = unique_orig_foods.loc[food_id]
    matched_content_df = content_df.loc[food_id]
    
    selected_foods = select_from_orig_foods(matched_unique_orig_foods, ingredient, matched_content_df)

    return selected_foods if not selected_foods.empty else pd.Series()

# %% ../../notebooks/09-molecule-db-finalising.ipynb 86
all_compounds = pd.Series(pd.NA, index=content_df.index.get_level_values(3).unique())

def calculate_content_averages(matched_content_df, full_content_series):
    mean_content = matched_content_df['concentration'].groupby('source_id').mean()
    return full_content_series.fillna(mean_content)
