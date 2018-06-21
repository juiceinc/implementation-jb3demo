import json
import time
from copy import deepcopy

from sqlalchemy import Column, String, ForeignKey, select, join

from dataservices.mixins import DownloadTable
from dataservices.recipe import *
from dataservices.redshift_connectionbase import *
from dataservices.servicebase import *
from dataservices.recipe_pool import RecipePool
from dataservices.renderers import OptionChooserRenderer
from dataservices.servicebasev3 import RecipeServiceBaseV3

# -------------
# Connect to the database
# -------------
from sqlalchemy.orm import relationship

from hashr.utils import hash_and_store_data

engine = redshift_create_engine()

# Instantiate the base class for declarative (table) class instances
# ------------------------------------------------------------------

Base = declarative_base()

current_milli_time = lambda: int(round(time.time() * 1000))

# -------------
# Step 1: Define the tables used in your application
# -------------



class DivLookup(Base):
    __table__ = Table('state_census_div_lookup', Base.metadata,
                      Column('census_division', String(), primary_key=True),
                      Column('name', String()),
                      schema='demo', extend_existing=True)


class StateFact(Base):
    """
    The `demo.census` table defined statically. This is the preferred way to do things
    as Juicebox starts up faster and can be more flexible.

    Again, a primary key is defined but will not be used.
    """
    __table__ = Table('state_fact', Base.metadata,
                      Column('id', String()),
                      Column('name', String(), primary_key=True),
                      Column('abbreviation', String()),
                      Column('country', String()),
                      Column('type', String()),
                      Column('sort', String()),
                      Column('status', String()),
                      Column('occupied', String()),
                      Column('notes', String()),
                      Column('fips_state', String()),
                      Column('assoc_press', String()),
                      Column('standard_federal_region', String()),
                      Column('census_region', String()),
                      Column('census_region_name', String()),
                      Column('census_division', String(),
                             ForeignKey(DivLookup.census_division)),
                      Column('census_division_name', String()),
                      Column('circuit_court', String()),
                      schema='demo', extend_existing=True)


class Census(Base):
    """
    The `demo.census` table defined statically. This is the preferred way to do things
    as Juicebox starts up faster and can be more flexible.

    Again, a primary key is defined but will not be used.
    """
    __table__ = Table('census', Base.metadata,
                      Column('state', String(30), ForeignKey(StateFact.name),
                             primary_key=True),
                      Column('sex', String(1)),
                      Column('age', Float()),
                      Column('pop2000', Float()),
                      Column('pop2008', Float()),
                      schema='demo', extend_existing=True)
    state_fact = relationship(StateFact)


# Another approach is to create a joined view
class CensusJoined(Base):
    __table__ = select([Census, StateFact]).select_from(
        join(Census, StateFact, Census.state == StateFact.name)).alias()


# -------------
# Step 2) Define a base class with metrics on the `metric_shelf` and dimensions
# on the dimension_shelf
# -------------



class CensusService(RecipeServiceBaseV3):
    # Metrics are defined as an SQLAlchemy expression, and a label.
    metric_shelf = {
        # formerly pop2000
        'requested': Metric(func.sum(Census.pop2000), label='Forms Requested',
                          format=".3s", singular="Form Requested",
                          plural="Forms Requested"),
        # formerly pop2008
        'newforms': Metric(func.sum(Census.pop2008), singular='New Forms Created',
                          format=".3s"),
        # formerly popdiff
        'exercised': Metric(func.sum(Census.pop2008 - Census.pop2000),
                          format=".3s",
                          singular='Privileges Exercised'),
        # formerly avgage
        'tempgrants': Metric(
            func.sum(Census.pop2008 * Census.age) / func.sum(Census.pop2008),
            singular='Temporary Privileges', format=".1f"),
        # formerly pctfemale
        # A metric using a complex expression
        'pctgranted': Metric(func.sum(
            case([(Census.sex == 'F', Census.pop2008)], else_=0)) / func.sum(
            Census.pop2008), format=".1%",
                            singular='% Granted'),
        # a metric using a formatter
        'pctdiff': Metric(func.sum(Census.pop2008 - Census.pop2000) / func.sum(
            Census.pop2000),
                          singular='Population Pct Change',
                          # formatters=[
                          #     lambda x: "Change is {0:0.1%} percent".format(
                          #         x)]
                              ),
    }

    # Dimensions are ways to split the data.
    dimension_shelf = {
        # Simplest possible dimension, a SQLAlchemy expression and a label.
        'state': Dimension(Census.state, singular='State', plural='States',
                           format=""),
        'first_letter_state': Dimension(func.substring(Census.state, 1, 1),
                                        label='State'),
        'age': Dimension(Census.age, singular='Age', plural='Ages'),
        'age_bands': Dimension(case([(Census.age < 21, 'Under 21'),
                                     (Census.age < 49, '21-49')
                                     ], else_='Other'), label='Age Bands'),
        # This will use the lookup to get display values of "M" and "F"
        # formerly sex--hacked to be a representation of status
        'endstatus': LookupDimension(Census.sex, singular='End Status', plural='End Status',
                               lookup={'M': 'Granted', "F": "Denied"}),
        # Formatters apply functions to the response
        'gender': Dimension(Census.sex, label='Sex',
                            formatters=[lambda x: ord(x), lambda x: x + 100]),
    }

    # Automatic filter keys are used for the global filters as well
    automatic_filter_keys = ('endstatus', 'state',)

    def __init__(self, *args, **kwargs):
        super(CensusService, self).__init__(*args, **kwargs)
        # self.Session = Session


# -------------
# Step 3) The data services response.
# -------------

class FilterService(CensusService):
    def build_response(self):
        self.metrics = ('requested', )
        recipes = []
        for dim in self.automatic_filter_keys:
            recipe = self.recipe().metrics(*self.metrics).dimensions(dim)
            recipes.append((recipe, dim))

        results = RecipePool(recipes).run()
        self.response['responses'] = results


class FirstChooserV3Service(CensusService):
    def build_response(self):
        start = current_milli_time()
        self.metrics = (
            # 'pop2000', 'pop2008',
            'exercised', 'tempgrants', 'pctgranted')
        recipe = self.recipe().metrics(*self.metrics)
        self.response['responses'].append(recipe.render(flavor='metric'))
        print 'Ms: ', current_milli_time() - start


class CardV3Service2(CensusService):
    def build_response(self):
        start = current_milli_time()

        self.metrics = ('exercised',)
        self.dimensions = ('state',)
        recipe1 = self.recipe().metrics(*self.metrics).dimensions(
            *self.dimensions)

        self.dimensions = ('endstatus', )
        recipe2 = self.recipe().metrics(*self.metrics).dimensions(
            *self.dimensions)

        results = RecipePool([
            (recipe1, 'States'), (recipe2, 'End Status'),
        ]).run()

        self.response['responses'] = results
        print 'Ms: ',current_milli_time() - start


class TableV3Service(DownloadTable, CensusService):
    def build_response(self):
        start = current_milli_time()
        self.metrics = ('requested', 'newforms', 'exercised')
        self.dimensions = ('state', 'endstatus')
        recipe1 = self.recipe().metrics(*self.metrics).dimensions(
            *self.dimensions)
        # self.dimensions = ('age_bands', 'age')
        # recipe2 = self.recipe().metrics(*self.metrics).dimensions(
        #     *self.dimensions)

        results = RecipePool([
            (recipe1, 'States'),
        ]).run()
        self.response['responses'] = results
        print 'Ms: ', current_milli_time() - start


# class SecondChooserV3Service(CensusService):
#     def build_response(self):
#         print 'Metrics: ',self.metrics
#         start = current_milli_time()
#         self.metrics = ('pop2000', )
#         self.dimensions = ('sex',)
#         recipe = self.recipe().dimensions(
#             *self.dimensions).metrics(*self.metrics)
#         self.response['responses'].append(recipe.render())
#         print 'Ms: ', current_milli_time() - start
#
#
# class ButtonChooserV3Service(CensusService):
#     def build_response(self):
#         render_config = {
#             'buttons': [
#                 {'total': 'total_label',
#                  'path': 'path1'},
#                 {'standard': 'standard_label',
#                  'path': 'path2'},
#                 {'vent_trach': 'Vent/Trach',
#                  'path': 'path3'}
#             ],
#             'group_by': 'exclusion'
#         }
#
#         renderer = OptionChooserRenderer(self, None, 'button_name')
#         response = renderer.render(flavor='buttons',
#                                    render_config=render_config)
#         self.response['responses'].append(response)
#
#
# class DistributionV3Service(CensusService):
#     def build_response(self):
#         start = current_milli_time()
#         self.metrics = ('pop2000', )
#         self.dimensions = ['age_bands', 'age']
#         recipe1 = self.recipe().dimensions(*self.dimensions) \
#             .metrics(*self.metrics).order_by(*self.dimensions).filters(
#             *self.filters)
#
#         self.dimensions = ['first_letter_state', 'state']
#
#         recipe2 = self.recipe().dimensions(*self.dimensions) \
#             .metrics(*self.metrics).order_by(*self.dimensions) \
#             .filters(*self.filters)
#         self.dimensions = ['gender', 'region']
#
#         results = RecipePool([
#             (recipe1, 'Ages'), (recipe2, 'States'),
#         ]).run()
#         self.response['responses'] = results
#         print 'Ms: ',current_milli_time() - start
#
#
#
# class LeaderboardV3Service(CensusService):
#     def build_response(self):
#         start = current_milli_time()
#         self.metrics = ('pop2000', 'pop2008', 'popdiff')
#         self.dimensions = ('state', )
#         recipe1 = self.recipe().metrics(*self.metrics).dimensions(
#             *self.dimensions)
#         self.dimensions = ('age', )
#         recipe2 = self.recipe().metrics(*self.metrics).dimensions(
#             *self.dimensions)
#
#         results = RecipePool([
#             (recipe1, 'States'), (recipe2, 'Ages'),
#         ]).run()
#         self.response['responses'] = results
#         print 'Ms: ', current_milli_time() - start
#
#
# class RankedListV3Service(CensusService):
#     def build_response(self):
#         start = current_milli_time()
#         self.metrics = ('avgage', 'pop2008')
#         self.dimensions = ('state', )
#         recipe1 = self.recipe().metrics(*self.metrics).dimensions(
#             *self.dimensions).order_by('avgage')
#         self.dimensions = ('sex',)
#         recipe2 = self.recipe().metrics(*self.metrics).dimensions(
#             *self.dimensions).order_by('avgage')
#         results = RecipePool([
#             (recipe1, 'States'), (recipe2, 'Gender'),
#         ]).run()
#         self.response['responses'] = results
#         print 'Ms: ',current_milli_time() - start
#
#
#
# class LollipopV3Service(CensusService):
#     def build_response(self):
#         start = current_milli_time()
#         self.metrics = ('pctfemale', 'pctdiff')
#         benchmark = self.recipe().dimensions().metrics(
#             *self.metrics).apply_global_filters(False)
#
#         recipe = self.recipe().metrics(*self.metrics).dimensions(
#             *self.dimensions).apply_global_filters(True).filters(
#             *self.filters).compare(benchmark)
#
#         self.response['responses'].append(
#             recipe.render(flavor='single_benchmark'))
#         print 'Ms: ',current_milli_time() - start
#
#
# class FreeFormV3Service1(CensusService):
#     def build_response(self):
#         start = current_milli_time()
#         self.metrics = ('popdiff', )
#         self.dimensions = ('state',)
#         recipe = self.recipe().metrics(*self.metrics).dimensions(
#             *self.dimensions).limit(1).apply_global_filters(False)
#         self.response['responses'].append(recipe.render())
#         print 'Ms: ',current_milli_time() - start
#
#
# class FreeFormV3Service2(CensusService):
#     def build_response(self):
#         start = current_milli_time()
#
#         data = {'name': 'Jason', 'pastry': 'cookies'}
#
#         response = self.response_template()
#         response['data'][0]['values'].append(data)
#
#         self.response['responses'].append(response)
#         print 'Ms: ',current_milli_time() - start
#
#
#
#
# class NineBoxV3Service(CensusService):
#     def build_response(self):
#         start = current_milli_time()
#
#         self.metrics = ('popdiff', 'pctfemale')
#         self.dimensions = ('state',)
#         recipe = self.recipe().metrics(*self.metrics).dimensions(
#             *self.dimensions).apply_global_filters(False)
#
#         self.response['responses'].append(recipe.render())
#         print 'Ms: ',current_milli_time() - start


# class MatchupV3Service(CensusService):
#     def build_response(self):
#         self.metrics = ('popdiff', )
#         self.dimensions = ('state',)
#
#         recipe = self.recipe().metrics(*self.metrics).dimensions(
#             *self.dimensions)
#
#         self.response['responses'].append(recipe.render())


# class StackSwitcherService(CensusService):
#     def __init__(self, *args, **kwargs):
#         super(StackSwitcherService, self).__init__(*args, **kwargs)
#         self.custom_filter_keys = self.automatic_filter_keys
#
#     def build_response(self):
#         hash_data = {
#             'id': '58c6a623',
#             'slug': 'census2',
#             'state': {
#                 'global_filters': {
#                     'values': {}
#                 }
#             }
#         }
#
#         global_filters = deepcopy(self.automatic_filters)
#         for k in self.automatic_filter_keys:
#             if k in self.custom_filters:
#                 global_filters[k] = [{'id': v} for v in self.custom_filters[k]]
#
#         hash_data['state']['global_filters']['values'] = global_filters
#         context_hash = hash_and_store_data(json.dumps(hash_data))
#
#         buttons = [
#             {
#                 'label': 'Census',
#                 'url': '/jb3demo/census#' + context_hash
#             }
#         ]
#
#         response = self.response_template()
#         response['data'][0]['values'] = buttons
#         self.response['responses'].append(response)
