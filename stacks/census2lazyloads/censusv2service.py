from __future__ import print_function
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
    __table__ = Table(
        "state_census_div_lookup",
        Base.metadata,
        Column("census_division", String(), primary_key=True),
        Column("name", String()),
        schema="demo",
        extend_existing=True,
    )


class StateFact(Base):
    """
    The `demo.census` table defined statically. This is the preferred way to do things
    as Juicebox starts up faster and can be more flexible.

    Again, a primary key is defined but will not be used.
    """

    __table__ = Table(
        "state_fact",
        Base.metadata,
        Column("id", String()),
        Column("name", String(), primary_key=True),
        Column("abbreviation", String()),
        Column("country", String()),
        Column("type", String()),
        Column("sort", String()),
        Column("status", String()),
        Column("occupied", String()),
        Column("notes", String()),
        Column("fips_state", String()),
        Column("assoc_press", String()),
        Column("standard_federal_region", String()),
        Column("census_region", String()),
        Column("census_region_name", String()),
        Column("census_division", String(), ForeignKey(DivLookup.census_division)),
        Column("census_division_name", String()),
        Column("circuit_court", String()),
        schema="demo",
        extend_existing=True,
    )


class Census(Base):
    """
    The `demo.census` table defined statically. This is the preferred way to do things
    as Juicebox starts up faster and can be more flexible.

    Again, a primary key is defined but will not be used.
    """

    __table__ = Table(
        "census",
        Base.metadata,
        Column("state", String(30), ForeignKey(StateFact.name), primary_key=True),
        Column("sex", String(1)),
        Column("age", Float()),
        Column("pop2000", Float()),
        Column("pop2008", Float()),
        schema="demo",
        extend_existing=True,
    )
    state_fact = relationship(StateFact)


# Another approach is to create a joined view
class CensusJoined(Base):
    __table__ = (
        select([Census, StateFact])
        .select_from(join(Census, StateFact, Census.state == StateFact.name))
        .alias()
    )


# -------------
# Step 2) Define a base class with metrics on the `metric_shelf` and dimensions
# on the dimension_shelf
# -------------


class CensusService(RecipeServiceBaseV3):
    # Metrics are defined as an SQLAlchemy expression, and a label.
    metric_shelf = {
        "pop2000": Metric(
            func.sum(Census.pop2000),
            label="Population 2000",
            format=".3s",
            singular="Population 2000",
            plural="Population 2000",
        ),
        "pop2008": Metric(
            func.sum(Census.pop2008), singular="Population 2008", format=".3s"
        ),
        "popdiff": Metric(
            func.sum(Census.pop2008 - Census.pop2000),
            format=".3s",
            singular="Population Growth",
        ),
        "avgage": Metric(
            func.sum(Census.pop2008 * Census.age) / func.sum(Census.pop2008),
            singular="Average Age",
            format=".1f",
        ),
        # A metric using a complex expression
        "pctfemale": Metric(
            func.sum(case([(Census.sex == "F", Census.pop2008)], else_=0))
            / func.sum(Census.pop2008),
            format=".1%",
            singular="% Female",
        ),
        # a metric using a formatter
        "pctdiff": Metric(
            func.sum(Census.pop2008 - Census.pop2000) / func.sum(Census.pop2000),
            singular="Population Pct Change",
            # formatters=[
            #     lambda x: "Change is {0:0.1%} percent".format(
            #         x)]
        ),
    }

    # Dimensions are ways to split the data.
    dimension_shelf = {
        # Simplest possible dimension, a SQLAlchemy expression and a label.
        "state": Dimension(Census.state, singular="State", plural="States", format=""),
        "first_letter_state": Dimension(
            func.substring(Census.state, 1, 1), label="State"
        ),
        "age": Dimension(Census.age, singular="Age", plural="Ages"),
        "age_bands": Dimension(
            case(
                [(Census.age < 21, "Under 21"), (Census.age < 49, "21-49")],
                else_="Other",
            ),
            label="Age Bands",
        ),
        # This will use the lookup to get display values of "M" and "F"
        "sex": LookupDimension(
            Census.sex,
            singular="Gender",
            plural="Genders",
            lookup={"M": "Menfolk", "F": "Womenfolk"},
        ),
        # Formatters apply functions to the response
        "gender": Dimension(
            Census.sex, label="Sex", formatters=[lambda x: ord(x), lambda x: x + 100]
        ),
    }

    # Automatic filter keys are used for the global filters as well
    automatic_filter_keys = (
        "sex",
        "state",
    )

    def __init__(self, *args, **kwargs):
        super(CensusService, self).__init__(*args, **kwargs)
        # self.Session = Session


# -------------
# Step 3) The data services response.
# -------------


class FilterService(CensusService):
    def build_response(self):
        self.metrics = ("pop2000",)
        recipes = []
        for dim in self.automatic_filter_keys:
            recipe = self.recipe().metrics(*self.metrics).dimensions(dim)
            recipes.append((recipe, dim))

        results = RecipePool(recipes).run()
        self.response["responses"] = results


class FirstChooserV3Service(CensusService):
    def build_recipe(self):
        start = current_milli_time()
        self.metrics = ("pop2000", "pop2008", "popdiff", "avgage", "pctfemale")
        recipe = self.recipe().metrics(*self.metrics).prepare(flavor="metric")
        print("Ms: ", current_milli_time() - start)
        return [recipe]
