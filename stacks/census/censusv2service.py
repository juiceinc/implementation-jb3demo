import time
from sqlalchemy import Column, String, ForeignKey, select, join

from dataservices.recipe import *
from dataservices.redshift_connectionbase import *
from dataservices.servicebase import *
from dataservices.recipe_pool import RecipePool
from dataservices.servicebasev3 import RecipeServiceBaseV3

# -------------
# Connect to the database
# -------------
from sqlalchemy.orm import relationship

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
        'pop2000': Metric(func.sum(Census.pop2000), label='Population 2000',
                          format=".3s", singular="Population 2000",
                          plural="Population 2000"),
        'pop2008': Metric(func.sum(Census.pop2008), singular='Population 2008',
                          format=".3s"),
        'popdiff': Metric(func.sum(Census.pop2008 - Census.pop2000),
                          format=".3s",
                          singular='Population Growth'),
        'avgage': Metric(
            func.sum(Census.pop2008 * Census.age) / func.sum(Census.pop2008),
            singular='Average Age', format=".1f"),
        # A metric using a complex expression
        'pctfemale': Metric(func.sum(
            case([(Census.sex == 'F', Census.pop2008)], else_=0)) / func.sum(
            Census.pop2008), format=".1%",
                            singular='% Female'),
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
        'state': Dimension(Census.state, singular='State', plural='States'),
        'first_letter_state': Dimension(func.substring(Census.state, 1, 1),
                                        label='State'),
        'age': Dimension(Census.age, singular='Age', plural='Ages'),
        'age_bands': Dimension(case([(Census.age < 21, 'Under 21'),
                                     (Census.age < 49, '21-49')
                                     ], else_='Other'), label='Age Bands'),
        # A dimension that requires a join, the join can be a relationship, or a table
        'region': Dimension(StateFact.standard_federal_region, label='Region',
                            join=StateFact),
        # A dimension that requires multiple joins
        'divname': Dimension(DivLookup.name, label='Census DivisionNames',
                             join=[DivLookup, StateFact]),
        'circuit_court': Dimension(StateFact.circuit_court,
                                   label='Circuit Court', join=StateFact),

        # This will use the lookup to get display values of "M" and "F"
        'sex': LookupDimension(Census.sex, singular='Gender', plural='Genders',
                               lookup={'M': 'Menfolk', "F": "Womenfolk"}),
        # Formatters apply functions to the response
        'gender': Dimension(Census.sex, label='Sex',
                            formatters=[lambda x: ord(x), lambda x: x + 100]),
    }

    # Automatic filter keys are used for the global filters as well
    automatic_filter_keys = ('sex', 'state',)
    default_metric = 'pop2000'

    def __init__(self, *args, **kwargs):
        super(CensusService, self).__init__(*args, **kwargs)
        # self.Session = Session


# -------------
# Step 3) The data services response.
# -------------

class FilterService(CensusService):
    def build_response(self):
        self.metrics = [self.default_metric]
        recipes = []
        for dim in self.automatic_filter_keys:
            recipe = self.recipe().metrics(*self.metrics).dimensions(dim)
            recipes.append((recipe, dim))

        results = RecipePool(recipes).run()
        self.response['responses'] = results


class FirstChooserV3Service(CensusService):
    def build_response(self):
        start = current_milli_time()
        self.metrics = ('pop2000', 'pop2008', 'popdiff', 'avgage', 'pctfemale')
        recipe = self.recipe().metrics(*self.metrics)
        self.response['responses'].append(recipe.render(flavor='metric'))
        print 'Ms: ', current_milli_time() - start


class SecondChooserV3Service(CensusService):
    def build_response(self):
        start = current_milli_time()
        self.dimensions = ('sex',)
        recipe = self.recipe().dimensions(
            *self.dimensions).metrics(*self.metrics)
        print 'len: ', len(self.dimensions)
        self.response['responses'].append(recipe.render(flavor='metric'))
        print 'Ms: ', current_milli_time() - start


class DistributionV3Service(CensusService):
    def build_response(self):
        start = current_milli_time()
        self.dimensions = ['age_bands', 'age']
        recipe1 = self.recipe().dimensions(*self.dimensions) \
            .metrics(*self.metrics).order_by(*self.dimensions).filters(
            *self.filters)

        self.dimensions = ['first_letter_state', 'state']

        recipe2 = self.recipe().dimensions(*self.dimensions) \
            .metrics(*self.metrics).order_by(*self.dimensions) \
            .filters(*self.filters)
        self.dimensions = ['gender', 'region']

        results = RecipePool([
            (recipe1, 'Ages'), (recipe2, 'States'),
        ]).run()
        self.response['responses'] = results
        print 'Ms: ',current_milli_time() - start


class TableV3Service(CensusService):
    def build_response(self):
        self.metrics = ('pop2000', 'pop2008', 'popdiff')
        self.dimensions = ('state', 'sex')
        recipe1 = self.recipe().metrics(*self.metrics).dimensions(
            *self.dimensions)
        self.dimensions = ('age_bands', 'age')
        recipe2 = self.recipe().metrics(*self.metrics).dimensions(
            *self.dimensions)

        results = RecipePool([
            (recipe1, 'States'), (recipe2, 'Ages'),
        ]).run()
        self.response['responses'] = results


class RankedListV3Service(CensusService):
    def build_response(self):
        self.metrics = ('avgage', 'pop2008')
        self.dimensions = ('state', )
        recipe1 = self.recipe().metrics(*self.metrics).dimensions(
            *self.dimensions).order_by('avgage')
        self.dimensions = ('sex',)
        recipe2 = self.recipe().metrics(*self.metrics).dimensions(
            *self.dimensions).order_by('avgage')
        results = RecipePool([
            (recipe1, 'States'), (recipe2, 'Gender'),
        ]).run()
        self.response['responses'] = results


class LollipopV3Service(CensusService):
    def build_response(self):
        self.metrics = ('pctfemale', 'pctdiff')
        benchmark = self.recipe().dimensions().metrics(
            *self.metrics).apply_global_filters(False)

        recipe = self.recipe().metrics(*self.metrics).dimensions(
            *self.dimensions).apply_global_filters(True).compare(benchmark)
        
        self.response['responses'].append(
            recipe.render(flavor='single_benchmark'))

