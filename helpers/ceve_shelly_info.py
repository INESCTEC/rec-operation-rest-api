# Hardcoded information about the shelly IDs from CEVE.
#
# REGARDING CONSUMPTION
# The user provides the main shelly ID that identifies a certain household. That shelly must always include the total
# liquid consumption of the house, either in one of its "phases", A, B, C (when mono-phase) or by summing the 3 phases
# (when tri-phase).
#
# REGARDING GENERATION
# For mono-phase households, if a PV panel is present, it can either have its own shelly or be measured in one of the
# identifying shelly's phases (A, B or C).
#
# DESCRIPTION
# {
# 	'name': the name of the CEVE member whose household harbors the shelly
# 	'phase': in which shelly phase, A, B, C or Total can we read the total liquid consumption
# }


CEVE_SHELLY_INFO = {
	'0cb815fd4dec': {
		'name': 'Nuno Meneses',
		'phase': 'total'
	},
	'0cb815fd4bcc': {
		'name': 'Jorge Azevedo',
		'phase': 'total'
	},
	'0cb815fc5350': {
		'name': 'Marco Sousa',
		'phase': 'a'
	},
	'0cb815fcc358': {
		'name': 'Bruno Sousa',
		'phase': 'a'
	},
	'34987a685128': {
		'name': 'Eduardo Azevedo',
		'phase': 'a'
	},
	'0cb815fcc31c': {
		'name': 'Nuno Vieira',
		'phase': 'total'
	},
	'0cb815fcf5b4': {
		'name': 'Fábio Coelho',
		'phase': 'a'
	},
	'0cb815fd15bc': {
		'name': 'Vicente Costa',
		'phase': 'total'
	},
	'0cb815fd4b30': {
		'name': 'José Barbosa',
		'phase': 'a'
	},
	'0cb815fc72bc': {
		'name': 'Ester Oliveira',
		'phase': 'total'
	},
	'0cb815fd3608': {
		'name': 'Luís Macedo',
		'phase': 'total'
	},
	'34987a675924': {
		'name': 'David Oliveira',
		'phase': 'total'
	},
	'0cb815fcc220': {
		'name': 'Arnaldo Faria / Jorge Faria',
		'phase': 'total'
	},
	'0cb815fc6178': {
		'name': 'Pedro Dourado',
		'phase': 'total'
	},
	'0cb815fd1d38': {
		'name': 'Victor Cruz',
		'phase': 'total'
	},
	'0cb815fd5654': {
		'name': 'Raquel Ferreira',
		'phase': 'total'
	},
	'0cb815fd534c': {
		'name': 'José Miguel',
		'phase': 'total'
	},
	'34987a676138': {
		'name': 'António Reis',
		'phase': 'total'
	},
	'34987a675060': {
		'name': 'Ana Maria Barbosa',
		'phase': 'total'
	},
	'0cb815fd49c4': {
		'name': 'Edgar Morgado',
		'phase': 'a'
	}
}
