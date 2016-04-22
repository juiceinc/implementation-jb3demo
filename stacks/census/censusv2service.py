import time
from sqlalchemy import Column, String, ForeignKey, select, join
from dataservices.connectionbase import regions

from dataservices.recipe import *
from dataservices.redshift_connectionbase import *
from dataservices.servicebase import *
from dataservices.recipe_pool import RecipePool
from dataservices import caching_query

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

class FirstDict(dict):
    """
    A dictionary with an added `first(key, default)` accessor that
    gets the first element in a list.
    """

    def first(self, key, default=None):
        value = self.get(key, default)
        if isinstance(value, (list, tuple)):
            return value[0]
        else:
            return value


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

class RecipeServiceBaseV3(object):
    """ A base class for Fruition Data Services using recipes

        Subclasses should define a dimension_shelf and metric_shelf
        """
    metric_shelf = {}
    dimension_shelf = {}
    filter_shelf = {}

    # A list of dimensions or metrics that will be automatically filtered
    # Gathered into self.automatic_filters (dict)
    automatic_filter_keys = ()
    # A list of dimensions or metrics that will be gathered into
    # self.custom_filters (dict)
    custom_filter_keys = ()

    def __init__(self, request, config, slice_type=None, user_filters=None,
                 stack_filters=None):
        self.request = request
        self.config = config
        self.slice_type = slice_type
        self.user_filters = user_filters
        self.stack_filters = stack_filters
        self.Session = sessionmaker(query_cls=caching_query.query_callable(regions),
                                    bind=engine)

        # Metrics, dimensions and filters to apply automatically to recipes
        self.metrics = []
        self.dimensions = []
        self.filters = []
        self.automatic_filters = FirstDict()
        self.custom_filters = FirstDict()

    @contextmanager
    def session_scope(self):
        """ Provide a transactional scope around a series of operations.
        """
        self.session = self.Session()
        try:
            yield self.session
            self.session.commit()
        except:
            self.session.rollback()
            raise
        finally:
            self.session.close()

    def recipe(self, *args, **kwargs):
        args = list(args)

        # Insert a reference to the service
        args.insert(0, self)

        # Use the default table if no table is passed and there is a
        # default_table defined
        if len(args) == 1 and hasattr(self, 'default_table'):
            args.append(self.default_table)

        return Recipe(*args, **kwargs)

    @property
    def global_filters(self):
        """ For backward compatability """
        return self.automatic_filters

    @property
    def local_filters(self):
        """ For backward compatability """
        return self.custom_filters

    def build_request_params(self):
        """ Build a dictionary of query parameters to use as global filters.
        Also keep a reference to any metric supplied.

        If a data service defines a list of local filter names
        `self.local_filter_ids`, then it will create a dictionary of the local
        filters along with their values in `self.local_filters`.
        """
        if self.request:
            params = self.request.data
        else:
            params = {}

        # Save the passed params
        self.params = params

        # Load the automatic filters
        self.automatic_filters.clear()
        for id in self.automatic_filter_keys:
            v = params.get(id, None)
            if v:
                self.automatic_filters[id] = v

        # Load the custom filters
        self.custom_filters.clear()
        for id in self.custom_filter_keys:
            v = params.get(id, None)
            if v:
                self.custom_filters[id] = v

        # for filter_ingredient in self.filter_ingredients:
        #     if filter_ingredient in params:
        #         filters.append(self.dimension_shelf[
        #                            filter_ingredient].filter_values(
        #             params[filter_ingredient])
        #                        )
        self.metrics = params.get('metric', [])
        self.dimensions = params.get('dimensions', [])

    def apply_user_filters(self, query=None, table=None):
        """ For recipe compatability, no longer used in jb3 """
        return query

    def apply_global_filters(self, query=None, table=None, limit_to=None):
        """ For recipe compatability, no longer used in jb3 """
        return query

    def build_response(self):
        """ Build the response.

        Subclasses should override this to do the following

        1) Evaluate local filters
        2) apply_user_filters on that query
        3) apply_global_filters on that query
        4) Apply local filters where needed
        5) Format the result and return it

        ----

        Built a recipe/ mapper from props in recipe to props in response
        a list of objects where each object has a group_by_type and id
        or a list of list of objects
        """
        pass

    def run(self):
        """ Process everything
        """
        self.response = {
            'responses': [],
            'version': '3'
        }

        with self.session_scope():
            self.build_request_params()
            self.build_response()


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
                          formatters=[
                              lambda x: "Change is {0:0.1%} percent".format(
                                  x)]),
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

def generate_default_filter_service(base):
    class DefaultFilterService(base):
        def build_response(self):
            for dim in self.automatic_filter_keys:
                recipe = self.recipe().metrics(self.default_metric).dimensions(
                    dim)
                self.response['responses'].append(recipe.render())


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
        self.response['responses'].append(recipe.render())
        print 'Ms: ',current_milli_time() - start

class SecondChooserV3Service(CensusService):
    def build_response(self):
        start = current_milli_time()
        self.dimensions = ('sex',)
        recipe = self.recipe().dimensions(
            *self.dimensions).metrics(*self.metrics)
        self.response['responses'].append(recipe.render())
        print 'Ms: ',current_milli_time() - start


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
