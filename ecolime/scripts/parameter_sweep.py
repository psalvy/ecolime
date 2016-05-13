import json
from os import system
import re

from cloudpickle import load, dump
from six import string_types

from minime.solve.algorithms import binary_search
from IPython import embed


def get_model():
    with open("prototype_51.pickle", "rb") as infile:
        model = load(infile)
    with open("prototype_51_expressions.pickle", "rb") as infile:
        expressions = load(infile)
    return model, expressions


def get_community_model():
    with open("prototype_community_GLUDy_CS.pickle", "rb") as infile:
        model = load(infile)
    with open("prototype_community_GLUDy_CS_expressions.pickle", "rb") as infile:
        expressions = load(infile)
    return model, expressions


def save_solution(model, filename_base):
    with open(filename_base + "_flux.json", "wb") as outfile:
        json.dump(model.get_metabolic_flux(), outfile)
    with open(filename_base + "_sol.pickle", "wb") as outfile:
        dump(model.solution, outfile)


def anaerobic_growth(model_file):
    model_name = model_file.rsplit(".", 1)[0]
    with open(model_file, "rb") as infile:
        me = load(infile)
    me.reactions.EX_o2_e.lower_bound = 0
    binary_search(me, max_mu=1.5, mu_accuracy=1e-15, verbose=True)
    save_solution(me, model_name + "_anaerobic")


def save_model(model, filename_base):
    with open(filename_base + "_model.pickle", "wb") as outfile:
        dump(model, outfile)


def unmodeled_protein_fraction(fraction):
    str_fraction = fraction
    fraction = float(fraction)
    model, expressions = get_model()
    model.unmodeled_protein_fraction = fraction
    binary_search(model, max_mu=1.5, mu_accuracy=1e-15, verbose=True,
                  compiled_expressions=expressions)
    save_solution(model, "unmodeled_protein_fraction_" + str_fraction)


def ngam(value):
    str_ngam = value
    ngam_value = float(value)
    model, expressions = get_model()
    model.unmodeled_protein_fraction = 0.45
    model.stoichiometric_data.ATPM.lower_bound = ngam_value
    for r in model.stoichiometric_data.ATPM.parent_reactions:
        r.update()
    binary_search(model, max_mu=1.5, mu_accuracy=1e-15, verbose=True,
                  compiled_expressions=expressions)
    save_solution(model, "ngam_" + str_ngam)


def limit_uptake(model):
    for r in model.reactions.query(re.compile("^EX_")):
        if r.id in {"EX_h2o_e", "EX_h_e", "EX_o2_e"}:
            continue
        r.lower_bound = max(-1, r.lower_bound)


def nutrient_limited_ngam(value):
    str_ngam = value
    ngam_value = float(value)
    model, expressions = get_model()
    limit_uptake(model)
    model.stoichiometric_data.ATPM.lower_bound = ngam_value

    for r in model.stoichiometric_data.ATPM.parent_reactions:
        r.update()
    binary_search(model, max_mu=1.5, mu_accuracy=1e-15, verbose=True,
                  compiled_expressions=expressions)
    save_solution(model, "limited_ngam_" + str_ngam)


def adjust_gam(me, GAM):
    gam_components = {
            "atp_c": -1 * GAM,
            "h2o_c": -1 * GAM,
            "adp_c": 1 * GAM,
            "h_c": 1 * GAM,
            "pi_c": 1 * GAM,
    }
    me.reactions.biomass_dilution.add_metabolites(gam_components,
                                                  combine=False)
    # this should probably be added to a biomass reaction class
    component_mass = sum(met.formula_weight / 1000. * -v for met, v in
                         me.reactions.biomass_dilution.metabolites.items() if
                         met.id != "biomass")
    me.reactions.biomass_dilution.add_metabolites(
        {'biomass': component_mass - 1}, combine=False)


def gam(value):
    str_gam = value
    GAM = float(value)
    me, expressions = get_model()
    me.unmodeled_protein_fraction = 0.45
    adjust_gam(me, GAM)
    binary_search(me, max_mu=1.5, mu_accuracy=1e-15, verbose=True,
                  compiled_expressions=expressions)
    save_solution(me, "gam_" + str_gam)


def adjust_global_parameter(me, parameter, multiplier):
    me.global_info[parameter] = me.global_info[parameter] * multiplier
    me.update()


def global_parameter(param_change):
    """
    param_change = str(parameter:multiplier)
    """

    parameter, str_multiplier = param_change.split(':')
    parameter_multiplier = float(str_multiplier)
    me, expressions = get_model()
    adjust_global_parameter(me, parameter, parameter_multiplier)
    binary_search(me, max_mu=1.5, mu_accuracy=1e-4, verbose=True)
    save_solution(me, parameter + "_" + str_multiplier)


def change_strain_fraction(me, fraction):
    for rxn in me.reactions.query('EX_'):
        # filter out a few complexes with 'COMPLEX_mod' in ID
        if 'EX_m' in rxn.id:
            continue

        check_rxn_id = rxn.id.replace('_S1', '_Shared').replace('_S2',
                                                                '_Shared')
        check_rxn = me.reactions.get_by_id(check_rxn_id)
        if check_rxn.lower_bound < 0:
            continue

        if '_S1' in rxn.id:
            met_id = rxn.id.replace('EX_', '').replace('_S1', '_Shared')
            rxn.add_metabolites({me.metabolites.get_by_id(met_id): fraction},
                                combine=False)
        elif '_S2' in rxn.id:
            met_id = rxn.id.replace('EX_', '').replace('_S2', '_Shared')
            rxn.add_metabolites({me.metabolites.get_by_id(met_id):
                                     (1-fraction)}, combine=False)


def strain_fractions(fraction_strain_1):
    """
    fraction
    """
    str_fraction_strain_1 = fraction_strain_1
    float_fraction_strain_1 = float(fraction_strain_1)
    me, expressions = get_community_model()
    change_strain_fraction(me, float_fraction_strain_1)
    binary_search(me, max_mu=1.5, mu_accuracy=1e-4, verbose=True)
    save_solution(me, "fraction_strain_1_" + str_fraction_strain_1)