/**
 * The DRZ/IAIS POI vocabulary, transcribed from the partner OpenAPI spec
 * (https://eve.iais.fraunhofer.de/poi/openapi.json, v0.0.5).
 *
 * `properties.subtype` is an anyOf over 13 separate string enums, so the subtype a POI may
 * carry depends on which group it belongs to. DRZ validates the string against the enum, so
 * these values are byte-exact copies of the spec and must not be "tidied up".
 */

export interface DrzSubtypeGroup {
    /** Schema name in the DRZ spec */
    key: string;
    /** What the operator sees in the picker */
    label: string;
    options: readonly string[];
}

/**
 * Which of the two secondary POI fields make sense for a category, and what affiliation the
 * category implies. Kept beside the catalog rather than spread through the dialog's JSX.
 *
 * A hidden field still sends `defaultMainType` / the current hazard level — DRZ requires both
 * — it is only kept off screen where it has no meaning: affiliation for a fire (a fire belongs
 * to no organisation), hazard level for a person, vehicle or animal.
 */
export interface DrzGroupRules {
    /** properties.type applied when this category is selected. */
    defaultMainType: string;
    hideMainType?: boolean;
    hideDangerLevel?: boolean;
}

const DRZ_GROUP_RULES: Record<string, DrzGroupRules> = {
    // 7 = Action. A fire is not an organisation, so it is filed under Action to get the right
    // icon in the partner software — the same value Argus has always sent for fire detections.
    Fire: { defaultMainType: "7", hideMainType: true },
    Person: { defaultMainType: "-1", hideDangerLevel: true },
    Vehicle: { defaultMainType: "-1", hideDangerLevel: true },
    Animal: { defaultMainType: "-1", hideDangerLevel: true },
};

/** Rules for a category; everything not listed shows both fields and implies no affiliation. */
export function drzGroupRules(groupKey: string | undefined): DrzGroupRules {
    return (groupKey && DRZ_GROUP_RULES[groupKey]) || { defaultMainType: "-1" };
}

export const DRZ_SUBTYPE_GROUPS: readonly DrzSubtypeGroup[] = [
    {
        key: "Person",
        label: "Person",
        options: [
            "Person",
            "Person in distress (trapped/buried)",
            "Person injured",
            "Person dead",
            "Missing person",
            "Buried person",
            "Presumably buried person",
        ],
    },
    {
        key: "Animal",
        label: "Animal",
        options: [
            "Animal",
            "Animal in distress (trapped/buried)",
            "Animal injured",
            "Animal dead",
        ],
    },
    {
        key: "Vehicle",
        label: "Vehicle",
        options: [
            "Land vehicle (car, truck, trailer)",
            "Rail vehicle (locomotive, wagon)",
            "Water vehicle (boat, ship)",
            "Air vehicle (airplane, helicopter)",
            "Helicopter",
        ],
    },
    {
        key: "DangerSymbol",
        label: "Danger symbol",
        options: [
            "Suspected (e.g., marked by AI)",
            "Confirmed (e.g., verified by image analyst)",
            "Fire hazard (small, medium, large)",
            "Explosion hazard",
            "CBRN hazard (Chemical, Biological, Radiological, and Nuclear)",
            "Electricity hazard (suspected POI for electrical installations, e.g., transformer house)",
            "Acute hazard from dangerous substances",
            "Hazard from dangerous substances",
            "Suspected hazard from dangerous substances",
        ],
    },
    {
        key: "Fire",
        label: "Fire",
        options: [
            "Fire (small)",
            "Fire (medium)",
            "Fire (large)",
        ],
    },
    {
        key: "Water",
        label: "Water",
        options: [
            "Small",
            "Medium",
            "Large",
        ],
    },
    {
        key: "Building",
        label: "Building",
        options: [
            "Building",
            "Building partially destroyed",
            "Building totally destroyed",
        ],
    },
    {
        key: "Fields",
        label: "Area / field",
        options: [
            "Fire (vegetation)",
            "Water (flood)",
            "Staging area",
            "Debris / destroyed building",
            "Passable areas?",
        ],
    },
    {
        key: "Dike",
        label: "Dike",
        options: [
            "Dike damage",
        ],
    },
    {
        key: "Other",
        label: "Other",
        options: [
            "Attribute partially blocked (road)",
            "Attribute blocked (road)",
            "Attribute damaged (building)",
            "Attribute partially destroyed (building)",
            "Attribute destroyed (building)",
            "Event",
            "Decontaminate",
            "Decontamination group equipment",
            "Explore",
            "Transport",
        ],
    },
    {
        key: "BuildingAccess",
        label: "Building access",
        options: [
            "Access open",
            "Access closed",
            "Access blocked",
            "Access paths (path)",
        ],
    },
    {
        key: "Hydrant",
        label: "Hydrant",
        options: [
            "Above ground",
            "Below ground",
        ],
    },
    {
        key: "StormWood",
        label: "Storm wood",
        options: [
            "Fallen tree / large branch",
        ],
    },
] as const;

/** Subtype -> the group that owns it, for prefilling the Category select from a stored value. */
export function findDrzGroup(subtype: string): DrzSubtypeGroup | undefined {
    return DRZ_SUBTYPE_GROUPS.find((g) => g.options.includes(subtype));
}

/**
 * `properties.type` — despite the name, this is the *organisation the object originates from*,
 * not a category of object. 1 is "fire brigade", not "a fire"; an actual fire is therefore filed
 * under 7 (Action), which is what makes the partner situational-awareness software draw the right
 * icon. Do not "correct" the per-class defaults below to match the object type — they are right.
 */
export const DRZ_MAIN_TYPES: readonly (readonly [string, string])[] = [
    ["1", "Fire brigade"],
    ["2", "USAR"],
    ["3", "EMS"],
    ["4", "Police"],
    ["5", "Army"],
    ["6", "Other"],
    ["7", "Action"],
    ["8", "CBuilding"],
    ["9", "Command"],
    ["10", "People"],
    ["11", "Resources"],
    ["12", "Active"],
    ["13", "ObjectManagement"],
    ["-1", "All / Unspecified"],
] as const;

export interface DrzClassDefault {
    /** DRZ_SUBTYPE_GROUPS key, or "" when the operator must choose */
    group: string;
    subtype: string;
    mainType: string;
}

/**
 * Prefill for the share dialog, keyed by Argus detection class. These reproduce what Argus has
 * always sent for fire/human/vehicle. "other" is deliberately blank: none of the 13 groups is a
 * defensible automatic match for "an object the operator marked", so it is an explicit choice and
 * the send stays disabled until it is made.
 */
export const DRZ_CLASS_DEFAULTS: Record<string, DrzClassDefault> = {
    human: { group: "Person", subtype: "Person", mainType: "-1" },
    vehicle: { group: "Vehicle", subtype: "Land vehicle (car, truck, trailer)", mainType: "-1" },
    fire: { group: "Fire", subtype: "Fire (medium)", mainType: "7" },
    other: { group: "", subtype: "", mainType: "-1" },
};

/** Match Argus class names loosely, the way the dialog always has (substring, case-insensitive). */
export function drzDefaultsForClass(className: string | undefined): DrzClassDefault {
    const cls = (className ?? "").toLowerCase();
    for (const key of Object.keys(DRZ_CLASS_DEFAULTS)) {
        if (key !== "other" && cls.includes(key)) return DRZ_CLASS_DEFAULTS[key];
    }
    return DRZ_CLASS_DEFAULTS.other;
}

/** properties.danger_level — SUSPECTED (false) / ACUTE (true). */
export const DRZ_DANGER_LEVELS: readonly (readonly [string, string])[] = [
    ["false", "Suspected"],
    ["true", "Acute"],
] as const;
