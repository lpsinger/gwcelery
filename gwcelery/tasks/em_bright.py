"""Qualitative source classification for CBC events."""
import io
import json

from ligo.skymap.io import events

from ..import app


def source_classification(m1, m2, c1, threshold=3.0):
    """This is the place-holder function for the source classfication pipeline.
    In the future, the actual source classification pipeline will be integrated
    in three steps. First step will be the simple integration of the
    point-estimate code that will be using the em_progenitors code from PyCBC.
    In the second step, rapid_pe needs to be made Python3 compatible so that
    the ambiguity ellipsoid feature can be brough back into action. And,
    finally the O3 implementation will be incorporated which is currently a
    work in progress. This placeholder code will only act upon the mass2 point
    estimate value and classify the systems as whether they have a neutron or
    not. It does not attempt to classify for the remnant mass, returns a NaN
    value for that probability."""
    if m2 <= threshold:
        return([100.0, 100.0])
    else:
        return([0.0, 0.0])


@app.task(shared=False)
def classifier(coinc_psd, graceid):
    """This function is currently actually calculating the simple
       source classification probability (m1 < 3.0 M_sun). In the
       future this code will call a classification code that will
       be put on lalinference.
    """
    # Parse event
    coinc, psd = coinc_psd
    coinc = io.BytesIO(coinc)
    psd = io.BytesIO(psd)
    event_source = events.ligolw.open(coinc, psd_file=psd, coinc_def=None)
    event, = event_source.values()

    # Run EM_Bright
    template_args = event.template_args
    mass1 = template_args['mass1']  # primary object mass
    mass2 = template_args['mass2']  # secondary object mass
    chi1 = template_args['spin1z']  # primary object aligned spin
    [p_ns, p_em] = source_classification(mass1, mass2, chi1)

    data = {
        'Prob NS2': p_ns,
        'Prob EMbright': p_em
    }

    return json.dumps(data)
