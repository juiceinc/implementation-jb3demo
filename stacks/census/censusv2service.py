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



class CensusService(RecipeServiceBase):
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
    def __init__(self, request, *args, **kwargs):
        # you're cut off
        self.Session = Session
        self.request = request
        self.download = False
        self.local_filter_ids = ()

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

    def run(self):
        """ Process everything
        """
        with self.session_scope():
            self.build_request_params()
            self.build_response()



class SecondChooserV3Service(CensusService):
    def __init__(self, request, *args, **kwargs):
        # you're cut off
        self.Session = Session
        self.request = request
        self.download = False
        self.local_filter_ids = ()

    def build_response(self):
        params = self.request.data
        metric = params.get('metric', ['pop2000'])[0]
        recipe = self.recipe().dimensions('sex').metrics(metric)

        response = recipe.jb_response("Sample")
        response['config'] = {"titleTemplate": "Cookies {}".format(randint(0, 10000))}

        group = {'items': [], 'group_by_type': 'metric', 'name': 'foo'}

        for row in recipe.all():
            group['items'].append({
                "id": row.sex_id,
                "label": row.sex,
                "group_by_type": 'sex',
                "formattedValue": "{0:.1f}".format(getattr(row,metric)/1000000.)
            })
        response['data'][0]['values'] = [group]

        self.response = {"responses": [response]}

    def run(self):
        """ Process everything
        """
        with self.session_scope():
            self.build_request_params()
            self.build_response()
