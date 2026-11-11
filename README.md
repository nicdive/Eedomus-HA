# eedomus pour Home Assistant

Intégration custom qui remonte **uniquement les capteurs et actionneurs que vous sélectionnez** depuis votre box eedomus — idéale pour garder eedomus comme **passerelle Z-Wave / RFX** tout en pilotant la maison depuis Home Assistant.

## Fonctionnalités

- Config Flow UI (pas de YAML obligatoire)
- Connexion cloud (`api.eedomus.com`) **ou** locale (`IP_DE_LA_BOX`)
- **Multi-sélection** des périphériques à l’installation
- Re-sélection à tout moment via **Configurer** (options)
- Mapping automatique vers :
  - `sensor` (température, humidité, lux, puissance, énergie…)
  - `binary_sensor` (mouvement, fumée, inondation, ouverture…)
  - `switch` / `light` / `cover`
- **Push webhook** pour une réactivité instantanée (mouvement, contact, RFX…)
- Polling de secours configurable (`0` = webhook seul, sinon 5 s → 15 min)
- Commandes actionneurs avec **mise à jour optimiste** (l’UI HA réagit tout de suite)

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
4. **Polling de secours** : `60` s par défaut (adapté aux règles de puissance / fin de cycle). Mettez `0` seulement si chaque capteur critique a une règle push eedomus → webhook HA. L’intégration lit la valeur live via `periph.caract` à chaque poll.

Pour modifier la sélection / voir l’URL webhook plus tard : ouvrir l’intégration → **Configurer**.

### Exemple : fin de cycle sèche-linge

1. Polling **30–60 s** (ou webhook sur le consomètre)
2. Automation HA — déclencheur *État numérique* :
   - Entité = consommation sèche-linge
   - Sous **20 W** pendant **5 minutes**
3. Sans webhook et avec un poll trop long (ex. 300 s / 0), la baisse de puissance arrive trop tard ou pas du tout → la règle ne part pas.

## Réactivité instantanée (webhook)

L’API eedomus ne pousse pas les changements toute seule. Configurez un **Actionneur HTTP** sur la box qui appelle Home Assistant dès qu’un périphérique change.

### 1. Récupérer l’URL

Dans HA : *Réglages → Appareils et services → eedomus → Configurer*.  
L’URL du webhook y est affichée, du type :

```text
http://IP_HOME_ASSISTANT:8123/api/webhook/xxxxxxxx
```

### 2. Créer l’actionneur HTTP eedomus

1. eedomus → **Automatismes → Actionneurs HTTP** (ou périphérique *Actionneur HTTP*)
2. URL, par exemple :
   ```text
   http://IP_HOME_ASSISTANT:8123/api/webhook/VOTRE_ID?periph_id=[PERIPH_ID]&value=[LAST_VALUE]
   ```
   Les jetons exacts dépendent de votre firmware / règle ; variantes acceptées :
   - `periph_id` / `periphId` / `id`
   - `value` / `last_value` / `val`
3. Méthode : **GET** (ou POST JSON)

### 3. Déclencher sur changement

Sur chaque périphérique critique (PIR, ouverture, RFX, **consomètre**…) créez une règle eedomus du type :

> *Quand la valeur change → appeler l’actionneur HTTP*

Vous pouvez aussi pousser une valeur déjà connue :

```text
.../api/webhook/VOTRE_ID?periph_id=123456&value=100
```

Ou forcer un refresh API :

```json
{"action": "refresh"}
```

```json
{"action": "refresh", "periph_id": "123456"}
```

Le webhook n’accepte que le **réseau local** (`local_only`).

### 4. Commandes depuis HA

Interrupteurs / lumières / volets : HA envoie l’ordre à eedomus (passerelle radio) et met à jour l’état **immédiatement**, puis vérifie via `periph.caract`.

## Identifiants API

Ne partagez jamais votre `api_secret`. Préférez l’API locale sur le réseau domestique. Ne publiez pas non plus l’ID du webhook.

## Limites

- Pas encore de climate / fil pilote / scènes dédiés (les usages non mappés tombent en `sensor`)
- RGBW avancé non géré (lampe dimmable 0–100 %)
- Le push nécessite une règle / actionneur HTTP côté eedomus (une fois par périphérique, ou via une macro générique)

Si vous avez besoin d’un usage_id précis non reconnu, ouvrez une issue avec un extrait anonymisé de `periph.list`.

## Licence

MIT
