import math

def compute_score(hands_data: dict):
	taker = hands_data["taker_team"]
	defender = "B" if taker == "A" else "A"
	final_score = {}
	flag_capot_fallen = 0
	flag_general_fallen = 0

	if hands_data["contract"] == "Capot":
		if hands_data[taker]["pre_score"] == 162:
			final_score = {taker: 500, defender: 0}
		else:
			final_score = {taker: 0, defender: 160 * 2}
			flag_capot_fallen = 1
	elif hands_data["contract"] == "Générale":
		if hands_data["general"] and hands_data[taker]["pre_score"] == 162 and hands_data["general"]:
			final_score = {taker: 750, defender: 0}
		else:
			final_score = {taker: 0, defender: 160 * 2}
			flag_general_fallen = 1
	else:
		if hands_data[taker]["pre_score"] < 81:
			final_score = {
					taker: 0,
					defender: 160 + int(hands_data["contract"])
				}
		else:
			belote_pts = 10 if hands_data["trump"] == "Tout atout" else 20
			temp_score = {"A": hands_data["A"]["pre_score"] + belote_pts * hands_data["A"]["belote"],
					"B": hands_data["B"]["pre_score"] + belote_pts * hands_data["B"]["belote"]}
			if temp_score[taker] >= int(hands_data["contract"]):
				final_score = {
					taker: int(hands_data["contract"]) + hands_data[taker]["pre_score"],
					defender: hands_data[defender]["pre_score"]
				}
			else:
				final_score = {
					taker: 0,
					defender: 160 + int(hands_data["contract"])
				}

		if hands_data[defender]["pre_score"] == 162:
			final_score[defender] += 90
		elif hands_data[taker]["pre_score"] == 162:
			final_score[taker] += 90
	

	mul = 2 if hands_data["coinche"] else (4 if hands_data["surcoinche"] else 1)
	if final_score[taker] == 0:
		final_score[defender] *= mul
	else:
		final_score[taker] *= mul

	if flag_capot_fallen:
		final_score[defender] += 90

	if flag_general_fallen:
		final_score[defender] += 90 * 2

	belote_pts = 10 if hands_data["trump"] == "Tout atout" else 20
	final_score["A"] += belote_pts * hands_data["A"]["belote"]
	final_score["B"] += belote_pts * hands_data["B"]["belote"]

	final_score[taker] = math.ceil(final_score[taker] / 10) * 10
	final_score[defender] = math.floor(final_score[defender] / 10) * 10

	return final_score