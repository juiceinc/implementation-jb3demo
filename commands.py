from jbcommands.builtincommands import Slice
from jbcommands.jbcommandbase import JBCommand


class MagicCommand(JBCommand):
    """"""
    class Meta:
        name = 'magic-insight'
        label = 'Magic Insight'
        icon = 'icon-magic-o'
        data_type = 'slice'
        context = 'slice'
        response_action = 'display'

    def execute(self):
        super(MagicCommand, self).execute()
        slice = Slice.objects.get(id=self.slice_id)

        recipe_response = slice.callable_data_service.datajb3(
            self.request,
            {
                'is_custom_command': True
            },
            slice_type=slice.slice_type.label
        )

        response_data = recipe_response['responses'][0]['data'][0]

        values_len = len(response_data['values'])

        highest_increase, highest_decrease = self._get_best_worst_values(response_data['values'])

        return '''
There are <strong>{total_value}</strong> buckets in this response.\n 
<strong>{highest_label}</strong> was your highest increase at <strong>{highest_percent}%</strong> 
from {highest_value} to {highest_benchmark} while <strong>{lowest_label}</strong> was your highest decrease, 
dropping <strong>{lowest_percent}%</strong> dropping from {lowest_value} to {lowest_benchmark}.
'''.format(
            total_value=values_len,
            highest_label=highest_increase['label'],
            highest_percent=highest_increase['increase_amount'],
            highest_value=highest_increase['value'],
            highest_benchmark=highest_increase['benchmark'],
            lowest_label=highest_decrease['label'],
            lowest_percent=100 - highest_decrease['decrease_amount'],
            lowest_value=highest_decrease['value'],
            lowest_benchmark=highest_decrease['benchmark']
        )

    @staticmethod
    def _get_best_worst_values(values):
        highest_increase = dict()
        highest_decrease = dict()

        for value in values:
            benchmark_value = value['benchmarks'][0]['value']

            # There was an increase in metric
            if benchmark_value > value['value']:
                increase_amount = float(benchmark_value) / float(value['value']) * 100
                if 'increase_amount' not in highest_increase or increase_amount > highest_increase['increase_amount']:
                    highest_increase = {
                        'increase_amount': round(increase_amount, 2),
                        'value': value['value'],
                        'benchmark': benchmark_value,
                        'label': value['label']
                    }

            elif benchmark_value < value['value']:
                decrease_amount = float(benchmark_value) / float(value['value']) * 100
                if 'decrease_amount' not in highest_decrease or decrease_amount < highest_decrease['decrease_amount']:
                    highest_decrease = {
                        'decrease_amount': round(decrease_amount, 2),
                        'value': value['value'],
                        'benchmark': benchmark_value,
                        'label': value['label']
                    }

        return highest_increase, highest_decrease

