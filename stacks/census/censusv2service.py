from copy import deepcopy

from sqlalchemy import Column, String, Integer, Float, case, ForeignKey, select, join, Table, or_
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dataservices.servicebase import *
from dataservices.recipe import *
from dataservices.redshift_connectionbase import *

# -------------
# Connect to the database
# -------------
from sqlalchemy.orm import relationship

engine = redshift_create_engine()

# Instantiate the base class for declarative (table) class instances
# ------------------------------------------------------------------

Base = declarative_base()


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
                      Column('census_division', String(), ForeignKey(DivLookup.census_division)),
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
                      Column('state', String(30), ForeignKey(StateFact.name), primary_key=True),
                      Column('sex', String(1)),
                      Column('age', Float()),
                      Column('pop2000', Float()),
                      Column('pop2008', Float()),
                      schema='demo', extend_existing=True)
    state_fact = relationship(StateFact)


# Another approach is to create a joined view
class CensusJoined(Base):
    __table__ = select([Census, StateFact]).select_from(join(Census, StateFact, Census.state == StateFact.name)).alias()


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
    global_filters = []
    local_filters = []

    def __init__(self, request, config, slice_type=None, user_filters=None, stack_filters=None):
        self.request = request
        self.config = config
        self.slice_type = slice_type
        self.user_filters = user_filters
        self.stack_filters = stack_filters
        self.Session = sessionmaker()

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

    def build_request_params(self):
        """ Build a dictionary of query parameters to use as global filters.
        Also keep a reference to any metric supplied.

        If a data service defines a list of local filter names
        `self.local_filter_ids`, then it will create a dictionary of the local
        filters along with their values in `self.local_filters`.
        """
        self.global_filters = {}
        self.local_filters = {}

    def apply_user_filters(self, query=None, table=None):
        return query

    def apply_global_filters(self, query=None, table=None, limit_to=None):
        return query

    def build_response(self):
        """ Build the response.

        Subclasses should override this to do the following

        1) Build one or more queries
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
        with self.session_scope():
            self.build_request_params()
            self.build_response()


class CensusService(RecipeServiceBaseV3):
    # Metrics are defined as an SQLAlchemy expression, and a label.
    metric_shelf = {
        'pop2000': Metric(func.sum(Census.pop2000), label='Population 2000', format=".2f", singular="cookie",
                          plural="cookies"),
        'pop2008': Metric(func.sum(Census.pop2008), label='Population 2008'),
        'popdiff': Metric(func.sum(Census.pop2008 - Census.pop2000), label='Population Growth'),
        'avgage': Metric(func.sum(Census.pop2008 * Census.age) / func.sum(Census.pop2008), label='Average Age'),
        # A metric using a complex expression
        'pctfemale': Metric(func.sum(case([(Census.sex == 'F', Census.pop2008)], else_=0)) / func.sum(Census.pop2008),
                            label='% Female'),
        # a metric using a formatter
        'pctdiff': Metric(func.sum(Census.pop2008 - Census.pop2000) / func.sum(Census.pop2000),
                          label='Population Pct Change',
                          formatters=[lambda x: "Change is {0:0.1%} percent".format(x)]),
    }

    # Dimensions are ways to split the data.
    dimension_shelf = {
        # Simplest possible dimension, a SQLAlchemy expression and a label.
        'state': Dimension(Census.state, label='State'),
        'age': Dimension(Census.age, label='Age'),
        'age_bands': Dimension(case([(Census.age < 21, 'Under 21'),
                                     (Census.age < 49, '21-49')
                                     ], else_='Other'), label='Age Bands'),
        # A dimension that requires a join, the join can be a relationship, or a table
        'region': Dimension(StateFact.standard_federal_region, label='Region', join=StateFact),
        # A dimension that requires multiple joins
        'divname': Dimension(DivLookup.name, label='Census DivisionNames', join=[DivLookup, StateFact]),
        'circuit_court': Dimension(StateFact.circuit_court, label='Circuit Court', join=StateFact),

        # This will use the lookup to get display values of "M" and "F"
        'sex': LookupDimension(Census.sex, label='Sex', lookup={'M': 'Menfolk', "F": "Womenfolk"}),
        # Formatters apply functions to the response
        'gender': Dimension(Census.sex, label='Sex', formatters=[lambda x: ord(x), lambda x: x + 100]),
    }

    # Dimension order will be used for the global filters
    dimension_order = ('sex', 'state',)
    default_metric = 'pop2000'
    default_table = Census

    def __init__(self, *args, **kwargs):
        super(CensusService, self).__init__(*args, **kwargs)
        self.Session = Session


# -------------
# Step 3) The data services response.
# -------------




class FirstChooserV3Service(CensusService):
    def build_response(self):
        metrics = ('pop2000', 'pop2008', 'popdiff', 'avgage', 'pctfemale')
        recipe = self.recipe().metrics(*metrics)

        response = recipe.jb_response("Sample")
        response['config'] = {"titleTemplate": "Moooooo {}".format(randint(0, 10000))}

        group = {'items': [], 'group_by_type': 'metric', 'name': 'metric'}

        for metric in metrics:
            group['items'].append({
                "id": metric,
                "label": self.metric_shelf[metric].id,
                "group_by_type": 'metric',
                "formattedValue": "250"
            })
        response['data'][0]['values'] = [group]

        self.response = {"responses": [response]}


class SecondChooserV3Service(CensusService):
    def build_response(self):
        params = self.request.data
        metric = params.get('metric', None)
        if metric:
            metric = metric[0]
        else:
            metric = 'pop2000'
        recipe = self.recipe().dimensions('sex').metrics(metric)

        response = recipe.jb_response("Sample")
        response['config'] = {"titleTemplate": "Cookies {}".format(randint(0, 10000))}

        group = {'items': [], 'group_by_type': 'metric', 'name': 'sex'}

        for row in recipe.all():
            group['items'].append({
                "id": row.sex_id,
                "label": row.sex,
                "group_by_type": 'sex',
                "formattedValue": "{0:.1f}".format(getattr(row, metric) / 1000000.)
            })
        response['data'][0]['values'] = [group]

        self.response = {"responses": [response]}


import abc


class AbstractResponseRenderer(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __init__(self, *args, **kwargs):
        pass

    @abc.abstractmethod
    def render(self, *args, **kwargs):
        pass

    def response_template(self):
        return {
            "data": [
                {
                    "name": "items",
                    "values": []
                }
            ],
            'config': {},
            'metadata': {},
            'template_context': {},
            'name': "Untitled",
        }


class DistributionRenderer(AbstractResponseRenderer):
    def __init__(self, service, data, group_dimension, grain_dimension, metrics):
        self.service = service
        self.data = data
        self.group_dimension = group_dimension
        self.grain_dimension = grain_dimension
        self.metrics = metrics

    def render(self):
        response = self.response_template()

        response['config'] = deepcopy(self.service.config)

        def make_group(label):
            return {
                'items': [],
                'label': label
            }

        group = make_group('__INITIAL__')
        for row in self.data:
            if group['label'] != getattr(row, self.group_dimension):
                group = make_group(getattr(row, self.group_dimension))
            item = {
                'group_by_type': self.grain_dimension,
                'id': getattr(row, self.grain_dimension + '_id'),
                'value': getattr(row, self.grain_dimension),
            }
            for metric in self.metrics:
                item[metric] = getattr(row, metric)
            group['items'].append(item)

        return response


class RenderFactory(object):
    __render_classes = {
        'distribution': DistributionRenderer,
    }

    @staticmethod
    def get_renderer(slice_type, *args, **kwargs):
        renderer_class = RenderFactory.__render_classes.get(slice_type, None)

        if renderer_class:
            return renderer_class(*args, **kwargs)
        raise NotImplementedError("The rendering engine for slice_type '{}' has not been implemented.".format(slice_type))


class DistributionV3Service(CensusService):
    def build_response(self):
        from copy import deepcopy

        params = self.request.data
        metric = params.get('metric', None)
        if metric:
            metric = metric[0]
        else:
            metric = 'pop2000'

        recipe = self.recipe().dimensions('age_bands', 'age').metrics(metric).order_by('age_bands', 'age')
        render_engine = RenderFactory.get_renderer(self.slice_type, self, recipe.all(), group_dimension='age_bank', grain_dimension='age',
                                                   metrics=[metric])


        self.response = {
            'responses': [render_engine.render()]
        }
        return











        # The first dimension is the group
        # the second dimension is the group_by_type
        # The metric is metric
        # recipe.jb_response(MAGIC)

        for row in recipe.all():
            print row._asdict()

        print self.slice_type

        # recipe = self.recipe(debug_ingredients=True).dimensions('region', 'state').metrics(metric).order_by('region', 'state')
        #
        # for row in recipe.all():
        #     print row._asdict()

        self.response = {
            "responses": [
                {
                    "name": "Age Bands",
                    "config": deepcopy(self.config),
                    "metadata": {},
                    "data": [
                        {
                            "name": "items",
                            "values": [
                                {
                                    "items": [
                                        {
                                            "group_by_type": "location",
                                            "id": "a-3",
                                            "value": 94,
                                            "label": "label-a-3"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "a-4",
                                            "value": 52,
                                            "label": "label-a-4"
                                        }
                                    ],
                                    "label": "Group 1"
                                },
                                {
                                    "items": [
                                        {
                                            "group_by_type": "location",
                                            "id": "b-3",
                                            "value": 98,
                                            "label": "label-b-3"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "b-4",
                                            "value": 65,
                                            "label": "label-b-4"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "b-5",
                                            "value": 12,
                                            "label": "label-b-5"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "b-6",
                                            "value": 79,
                                            "label": "label-b-6"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "b-7",
                                            "value": 28,
                                            "label": "label-b-7"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "b-8",
                                            "value": 8,
                                            "label": "label-b-8"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "b-9",
                                            "value": 35,
                                            "label": "label-b-9"
                                        }
                                    ],
                                    "label": "Group 2"
                                }
                            ]
                        }
                    ]
                },
                {
                    "name": "States by Region",
                    "config": deepcopy(self.config),
                    "metadata": {},
                    "data": [
                        {
                            "name": "items",
                            "values": [
                                {
                                    "items": [
                                        {
                                            "group_by_type": "location",
                                            "id": "a-3",
                                            "value": 14,
                                            "label": "label-a-3"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "a-4",
                                            "value": 63,
                                            "label": "label-a-4"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "a-5",
                                            "value": 97,
                                            "label": "label-a-5"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "a-6",
                                            "value": 100,
                                            "label": "label-a-6"
                                        }
                                    ],
                                    "label": "Group AAA"
                                },
                                {
                                    "items": [
                                        {
                                            "group_by_type": "location",
                                            "id": "b-3",
                                            "value": 74,
                                            "label": "label-b-3"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "b-4",
                                            "value": 19,
                                            "label": "label-b-4"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "b-5",
                                            "value": 38,
                                            "label": "label-b-5"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "b-6",
                                            "value": 54,
                                            "label": "label-b-6"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "b-7",
                                            "value": 0,
                                            "label": "label-b-7"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "b-8",
                                            "value": 57,
                                            "label": "label-b-8"
                                        }
                                    ],
                                    "label": "Group BBB"
                                },
                                {
                                    "items": [
                                        {
                                            "group_by_type": "location",
                                            "id": "c-3",
                                            "value": 81,
                                            "label": "label-c-3"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "c-4",
                                            "value": 26,
                                            "label": "label-c-4"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "c-5",
                                            "value": 62,
                                            "label": "label-c-5"
                                        },
                                        {
                                            "group_by_type": "location",
                                            "id": "c-6",
                                            "value": 3,
                                            "label": "label-c-6"
                                        }
                                    ],
                                    "label": "Group CCC"
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        self.response['responses'][1]['config']['titleTemplate'] = 'Cookie Monster'
