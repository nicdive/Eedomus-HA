# eedomus pour Home Assistant

Intégration custom qui remonte **uniquement les capteurs et actionneurs que vous sélectionnez** depuis votre box eedomus — sur le même principe que brancher une 2ᵉ instance Home Assistant.

## Fonctionnalités

- Config Flow UI (pas de YAML obligatoire)
- Connexion cloud (`api.eedomus.com`) **ou** locale (`IP_DE_LA_BOX`)
- **Multi-sélection** des périphériques à l’installation
- Re-sélection à tout moment via **Configurer** (options)
- Mapping automatique vers :
  - `sensor` (température, humidité, lux, puissance, énergie…)
  - `binary_sensor` (mouvement, fumée, inondation, ouverture…)
  - `switch` / `light` / `cover`
- Polling configurable (15 s → 15 min)

## Installation

### Manuelle

1. Copiez le dossier `custom_components/eedomus` dans la config Home Assistant :
   ```
   /config/custom_components/eedomus/
   ```
2. Redémarrez Home Assistant
3. **Réglages → Appareils et services → Ajouter une intégration → eedomus**

### HACS

1. Ajoutez ce dépôt en dépôt personnalisé (catégorie *Integration*)
2. Installez **eedomus**
3. Redémarrez, puis ajoutez l’intégration

## Configuration

1. **Hôte API**
   - Local recommandé : `192.168.x.x` (IP de la box)
   - Cloud : `api.eedomus.com`
2. **Identifiant / mot de passe API**  
   Dans eedomus : *Configuration → Mon compte → API utilisateur*
3. Choisissez les périphériques à importer dans la liste

Pour modifier la sélection plus tard : ouvrir l’intégration → **Configurer**.

## Identifiants API

Ne partagez jamais votre `api_secret`. Préférez l’API locale sur le réseau domestique.

## Limites (v1)

- Pas encore de climate / fil pilote / scènes dédiés (les usages non mappés tombent en `sensor`)
- Pas de push webhook (polling uniquement)
- RGBW avancé non géré (lampe dimmable 0–100 %)

Si vous avez besoin d’un usage_id précis non reconnu, ouvrez une issue avec un extrait anonymisé de `periph.list`.

## Licence

MIT
