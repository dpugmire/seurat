"""State for loaded preference profiles and actionable suggestions."""


def defaults():
    return {
        "preferenceMode": "off",
        "preferenceProfileLoaded": False,
        "preferenceProfileStatus": "",
        "preferenceWorkspaceSuggestionsAvailable": False,
        "showPreferenceSuggestion": False,
        "preferenceSuggestionId": "",
        "preferenceSuggestionType": "",
        "preferenceSuggestionTitle": "",
        "preferenceSuggestionMessage": "",
        "preferenceSuggestionVariableId": "",
        "preferenceSuggestionCurrentVisualization": "",
        "preferenceSuggestionRecommendedVisualization": "",
        "preferenceSuggestionCellIndex": -1,
        "preferenceSuggestionPaneId": "",
        "preferenceSuggestionTabId": "",
        "preferenceSuggestionVariables": [],
        "preferenceSuggestionConfidence": 0.0,
        "preferenceSuggestionEvidenceCount": 0.0,
        "preferenceSuggestionSessionCount": 0,
        "preferenceSuggestionStatus": "",
    }
