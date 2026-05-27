// Intake field registry for the consultant form (a minimal stand-in for the
// T06-02 field registry). The manual jurisdiction/overlay entry is the GIS
// fallback (AGENTS.md GIS Intake Strategy) until real detection lands (SAAS-06).

import type { JurisdictionEntry } from './types';

export const PROJECT_TYPES = [
  'transmission_line',
  'substation',
  'utility_corridor',
  'roadside_utility',
  'linear_general',
  'pipeline',
];

export const PROJECT_BOOLEANS = [
  'federal_nexus',
  'dredge_or_fill_in_waters',
  'stormwater_discharge_to_surface_water',
  'federal_water_permit_or_license',
  'usace_permit_required',
  'work_in_navigable_waters',
  'municipal_row_use',
  'fill_placement',
  'land_use_not_permitted_by_right',
  'special_use_requested',
];

export const PROJECT_NUMBERS = [
  'stream_crossings_count',
  'disturbed_acres',
  'structure_height_ft_agl',
  'utility_row_crossings_count',
];

export const DERIVED_BOOLEANS = ['major_federal_action', 'may_affect_listed_species'];

export const OVERLAY_BOOLEANS = [
  'wetlands_present',
  'waters_of_us_present',
  'navigable_waters_present',
  'fema_floodplain',
  'floodway',
];

const MUNICIPALITY = (id: string, name: string): JurisdictionEntry => ({
  jurisdiction_id: `us-tx-municipality-${id}`,
  jurisdiction_level: 'municipality',
  canonical_name: `City of ${name}`,
});

export const JURISDICTIONS: JurisdictionEntry[] = [
  { jurisdiction_id: 'us', jurisdiction_level: 'federal', canonical_name: 'United States' },
  { jurisdiction_id: 'us-tx', jurisdiction_level: 'state', canonical_name: 'Texas' },
  MUNICIPALITY('houston', 'Houston'),
  MUNICIPALITY('dallas', 'Dallas'),
  MUNICIPALITY('austin', 'Austin'),
  MUNICIPALITY('san-antonio', 'San Antonio'),
  MUNICIPALITY('fort-worth', 'Fort Worth'),
  MUNICIPALITY('arlington', 'Arlington'),
  MUNICIPALITY('waco', 'Waco'),
  MUNICIPALITY('el-paso', 'El Paso'),
];

export interface IntakeState {
  projectType: string;
  booleans: Record<string, boolean>;
  numbers: Record<string, string>;
  derived: Record<string, boolean>;
  overlays: Record<string, boolean>;
  jurisdictionIds: string[];
}

export function emptyIntake(): IntakeState {
  return {
    projectType: PROJECT_TYPES[0],
    booleans: {},
    numbers: {},
    derived: {},
    overlays: {},
    jurisdictionIds: ['us', 'us-tx'],
  };
}

// Prefill matching the federal-nexus benchmark — the quickest path to a
// 5-permit matrix when walking the flow manually.
export function federalNexusPrefill(): IntakeState {
  return {
    projectType: 'transmission_line',
    booleans: {
      federal_nexus: true,
      dredge_or_fill_in_waters: true,
      stormwater_discharge_to_surface_water: true,
      federal_water_permit_or_license: true,
      usace_permit_required: true,
      work_in_navigable_waters: false,
    },
    numbers: { stream_crossings_count: '2', disturbed_acres: '5', structure_height_ft_agl: '150' },
    derived: { major_federal_action: true, may_affect_listed_species: true },
    overlays: {
      wetlands_present: true,
      waters_of_us_present: true,
      navigable_waters_present: false,
      fema_floodplain: false,
    },
    jurisdictionIds: ['us', 'us-tx'],
  };
}
