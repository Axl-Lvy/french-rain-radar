# Data sources

All data comes from **Météo-France**, distributed under the [Licence Ouverte / Etalab](https://www.etalab.gouv.fr/licence-ouverte-open-licence/). You need a free API token from <https://portail-api.meteofrance.fr/>.

## Products used

| Product | Purpose | Resolution | Cadence | Forecast range |
|---|---|---|---|---|
| PRECIP-FRANCE (radar mosaic) | Observed precipitation | ~1 km | 5 min | observed |
| AROME-NWC | Numerical weather forecast for the very near term | 1.3 km | hourly runs, ~15-min timesteps | 0–6 h |

The pipeline composes:

- **radar layer** → past observed frames from the radar mosaic (used for "now" and the recent history scrubber)
- **nowcast layer** → 0–60 min generated locally via `pysteps` optical-flow extrapolation on the latest 4–6 radar frames
- **forecast layer** → 1–6 h from AROME-NWC

The transition between nowcast and AROME-NWC is blended around 45–75 min using linear weights, so the timeline appears continuous to the user.

## Projection note

Météo-France grids are in **Lambert-93 (EPSG:2154)**. The pipeline reprojects to **Web Mercator (EPSG:3857)** so the resulting PNGs drop onto a MapLibre map without further transformation.

## Useful reference URLs

- Modern API portal: <https://portail-api.meteofrance.fr/>
- Open-data portal (datasets, docs): <https://meteo.data.gouv.fr/>
- Legacy portal (kept here for archaeology): <https://donneespubliques.meteofrance.fr/?fond=produit&id_produit=307&id_rubrique=34>

## Terms of use

The Licence Ouverte permits free reuse, redistribution, and adaptation, including commercial use, as long as Météo-France is credited. The client UI must surface "Source: Météo-France" somewhere visible.
