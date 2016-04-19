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
    dimensions = {}
    filter_shelf = {}
    global_filters = []
    local_filters = []
    global_filter_ids = ()

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
        if self.request:
            params = self.request.data
        else:
            params = {}
        self.params = params
        # Build the global filters.
        self.global_filters = {}
        for id in self.global_filter_ids:
            v = params.get(id, None)
            if v:
                self.global_filters[id] = v

        # self.global_filters = {k: [unquote_plus(_) for _ in v] for
        #                        k, v in self.global_filters.iteritems()}
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
        'pop2000': Metric(func.sum(Census.pop2000), label='Population 2000', format=".3s", singular="cookie",
                          plural="cookies"),
        'pop2008': Metric(func.sum(Census.pop2008), label='Population 2008', format=".3s"),
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
        'state': Dimension(Census.state, singular='State', plural='States'),
        'first_letter_state': Dimension(func.substring(Census.state,1,1), label='State'),
        'age': Dimension(Census.age, singular='Age', plural='Ages'),
        'age_bands': Dimension(case([(Census.age < 21, 'Under 21'),
                                     (Census.age < 49, '21-49')
                                     ], else_='Other'), label='Age Bands'),
        # A dimension that requires a join, the join can be a relationship, or a table
        'region': Dimension(StateFact.standard_federal_region, label='Region', join=StateFact),
        # A dimension that requires multiple joins
        'divname': Dimension(DivLookup.name, label='Census DivisionNames', join=[DivLookup, StateFact]),
        'circuit_court': Dimension(StateFact.circuit_court, label='Circuit Court', join=StateFact),

        # This will use the lookup to get display values of "M" and "F"
        'sex': LookupDimension(Census.sex, singular='Gender', plural='Genders', lookup={'M': 'Menfolk', "F": "Womenfolk"}),
        # Formatters apply functions to the response
        'gender': Dimension(Census.sex, label='Sex', formatters=[lambda x: ord(x), lambda x: x + 100]),
    }

    # Dimension order will be used for the global filters
    global_filter_ids = ('sex', 'state',)
    default_metric = 'pop2000'
    default_table = Census

    def __init__(self, *args, **kwargs):
        super(CensusService, self).__init__(*args, **kwargs)
        self.Session = Session


# -------------
# Step 3) The data services response.
# -------------

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


class OptionChooserRenderer(AbstractResponseRenderer):
    def __init__(self, service, data, name, dimensions, metrics, metadata):
        self.service = service
        self.data = data
        self.name = name
        self.dimensions = dimensions
        self.metrics = metrics
        self.metadata = metadata

    def render(self):
        response = self.response_template()
        response['name'] = self.name
        response['config'] = deepcopy(self.service.config)

        row = self.data[0]

        # Generate a list of labels
        labels = [self.metadata[metric]['label_plural'] for metric in
                  self.metrics]

        if len(self.metrics) > 1:
            group = {'items': [], 'group_by_type': 'metric', 'name': 'metric'}
            self.metrics = zip(self.metrics, labels)
            for metric, label in self.metrics:
                group['items'].append({
                    "id": metric,
                    "label": label,
                    "group_by_type": 'metric',
                    "value": getattr(row, metric)
                })
            response['data'][0]['values'].append(group)
            metadata = {}
        else:
            metric = self.metrics[0]
            group = {'items': [], 'group_by_type': labels[0],
                     'name': labels[0]}

            for row in self.data:
                group['items'].append({
                    "id": getattr(row, self.dimensions[0] + '_id'),
                    "label": getattr(row, self.dimensions[0]),
                    "group_by_type": self.dimensions[0],
                    "value": getattr(row, metric)
                })
            response['data'][0]['values'] = [group]

            metadata = {
                'value': self.metadata[metric],
            }

        response['metadata'] = metadata

        return response


class DistributionRenderer(AbstractResponseRenderer):

    def __init__(self, service, data, name, dimensions, metrics, metadata):
        self.service = service
        self.data = data
        self.name = name
        self.dimensions = dimensions
        self.metrics = metrics
        self.metadata = metadata

    def render(self):
        response = self.response_template()
        response['name'] = self.name
        response['config'] = deepcopy(self.service.config)

        # Determine the roles using the order of keys
        # passed in dimensions and metrics
        group_dimension = self.dimensions[0]
        grain_dimension = self.dimensions[1]
        value_metric = self.metrics[0]

        from itertools import groupby
        from operator import attrgetter
        for group, items in groupby(self.data, attrgetter(group_dimension)):
            group_data = {
                'items': [],
                'label': group
            }

            for item in items:
                item_data = {
                    'group_by_type': grain_dimension,
                    'id': getattr(item, grain_dimension + '_id'),
                    'label': getattr(item, grain_dimension),
                    'value': getattr(item, value_metric),
                }
                group_data['items'].append(item_data)

            response['data'][0]['values'].append(group_data)

        metadata = {
            'value': self.metadata[value_metric],
        }
        response['metadata'] = metadata

        return response


class FiltersRenderer(AbstractResponseRenderer):
    def __init__(self, service, data, name, dimensions, metrics,
                 metadata):
        self.service = service
        self.data = data
        self.name = name
        self.dimensions = dimensions
        self.metrics = metrics
        self.metadata = metadata

    def render(self):
        response = self.response_template()
        response['config'] = deepcopy(self.service.config)

        # Determine the roles using the order of keys
        # passed in dimensions and metrics
        dimension = self.dimensions[0]
        count_metric = self.metrics[0]

        filter_items = {'values': [],
                        'group_by_type': dimension,
                        'name': 'items'}

        for item in self.data:
            item_data = {
                'id': getattr(item, dimension + '_id'),
                'name': getattr(item, dimension),
                'group_by_type': dimension,
                'count': getattr(item, count_metric),
            }
            for metric in self.metrics[1:]:
                item_data[metric] = getattr(item, metric)
            filter_items['values'].append(item_data)

        response['data'][0] = filter_items
        response['name'] = self.metadata[dimension]['label_plural']

        self.metadata['count'] = self.metadata[count_metric]
        response['metadata'] = self.metadata

        return response


class RenderFactory(object):
    __render_classes = {
        'distribution': DistributionRenderer,
        'filters': FiltersRenderer,
        'option-chooser': OptionChooserRenderer,
    }

    @staticmethod
    def get_renderer(slice_type, *args, **kwargs):
        renderer_class = RenderFactory.__render_classes.get(slice_type, None)

        if renderer_class:
            return renderer_class(*args, **kwargs)
        raise NotImplementedError(
            "The rendering engine for slice_type '{}' has not been implemented.".format(slice_type))


def generate_default_filter_service(base):

    class DefaultFilterService(base):

            def build_response(self):
                metrics = [self.default_metric]
                self.response = {
                    'responses': []
                }
                for dim in self.global_filter_ids:
                    dimension = self.dimension_shelf[dim]
                    recipe = self.recipe().metrics(self.default_metric).dimensions(
                        dim)
                    render_engine = RenderFactory.get_renderer(self.slice_type,
                                                               self,
                                                               metrics, dim,
                                                               dimension.label,
                                                               recipe.all(),
                                                               recipe.metadata)
                    self.response['responses'].append(render_engine.render())


class FilterService(CensusService):

    def build_response(self):
        metrics = [self.default_metric]
        self.response = {
            'responses': []
        }
        for dim in self.global_filter_ids:
            recipe = self.recipe().metrics(*metrics).dimensions(dim)
            # metadata = recipe.metadata(metrics, [dim])
            metadata = recipe.metadata(self)

            render_engine = RenderFactory.get_renderer(self.slice_type,
                                                       self,
                                                       recipe.all(),
                                                       "foo",
                                                       [dim],
                                                       metrics,
                                                       metadata)
            self.response['responses'].append(render_engine.render())


class FirstChooserV3Service(CensusService):
    def build_response(self):
        metrics = ('pop2000', 'pop2008', 'popdiff', 'avgage', 'pctfemale')

        recipe = self.recipe().metrics(*metrics)

        metadata = recipe.metadata(self)
        render_engine = RenderFactory.get_renderer(self.slice_type,
                                                   self,
                                                   recipe.all(),
                                                   name="FirstChooser",
                                                   dimensions=[],
                                                   metrics=metrics,
                                                   metadata=metadata)
        self.response = {
            'responses': [render_engine.render()]
        }


class SecondChooserV3Service(CensusService):
    def build_response(self):
        params = self.request.data
        metric = params.get('metric', None)
        if metric:
            metric = metric[0]
        else:
            metric = 'pop2000'
        metrics = [metric]
        dimensions = ['sex', ]
        recipe = self.recipe().dimensions(*dimensions).metrics(*metrics)

        metadata = recipe.metadata(self)
        render_engine = RenderFactory.get_renderer(self.slice_type,
                                                   self,
                                                   recipe.all(),
                                                   name="SecondChooser",
                                                   dimensions=dimensions,
                                                   metrics=metrics,
                                                   metadata=metadata)
        self.response = {
            'responses': [render_engine.render()]
        }


class DistributionV3Service(CensusService):
    def build_response(self):
        params = self.request.data
        metric = params.get('metric', None)
        if metric:
            metric = metric[0]
        else:
            metric = 'pop2000'

        metrics = [metric]
        filters = []

        if 'sex' in params:
            if params['sex']:
                filters.append(self.dimension_shelf['sex'].filter_values(params['sex']))

        recipe = self.recipe().dimensions('age_bands', 'age') \
            .metrics(*metrics).order_by('age_bands', 'age').filters(*filters)

        metadata = recipe.metadata(self)

        render_engine = RenderFactory.get_renderer(self.slice_type,
                                                   self,
                                                   recipe.all(),
                                                   name="Ages",
                                                   dimensions=('age_bands', 'age'),
                                                   metrics=metrics,
                                                   metadata=metadata)
        self.response = {
            'responses': [render_engine.render()]
        }

        recipe = self.recipe().dimensions('first_letter_state', 'state') \
            .metrics(*metrics).order_by('first_letter_state', 'state') \
            .filters(*filters)

        metadata = recipe.metadata(self)
        render_engine = RenderFactory.get_renderer(self.slice_type,
                                                   self,
                                                   recipe.all(),
                                                   name="States",
                                                   dimensions=('first_letter_state', 'state'),
                                                   metrics=metrics,
                                                   metadata=metadata)
        self.response['responses'].append(render_engine.render())

        # self.response = {
        #     'responses': [self.recipe().dimensions('age_bands', 'age').metrics(metric).order_by('age_bands', 'age').filters(*filters).render()
        #                   self.recipe().dimensions('first_letter_state', 'state').metrics(metric).order_by(
        #                       'first_letter_state', 'state').filters(*filters).render()]
        # }


