import os
import pandas as pd
from pybaseball import statcast_pitcher
import matplotlib.pyplot as plt

def get_pre_post_windows(player_id: int, tj_date, return_date, window_pitches=300):
    pre_data = statcast_pitcher(
        start_dt=(tj_date - pd.Timedelta(days=365)).strftime("%Y-%m-%d"),
        end_dt=tj_date.strftime("%Y-%m-%d"),
        player_id=player_id
    ).sort_values("game_date")

    post_data = statcast_pitcher(
        start_dt=return_date.strftime("%Y-%m-%d"),
        end_dt=(return_date + pd.Timedelta(days=365)).strftime("%Y-%m-%d"),
        player_id=player_id
    ).sort_values("game_date")

    if len(pre_data) < window_pitches or len(post_data) < window_pitches:
        return None, None, len(pre_data), len(post_data)

    pre_window = pre_data.tail(window_pitches).copy()
    post_window = post_data.head(window_pitches).copy()

    return pre_window, post_window, len(pre_data), len(post_data)

def fastball_velo_change(pre_df, post_df):
    pre_ff = pre_df[pre_df["pitch_type"] == "FF"]
    post_ff = post_df[post_df["pitch_type"] == "FF"]

    if len(pre_ff) == 0 or len(post_ff) == 0:
        return None

    pre_velo = pre_ff["release_speed"].mean()
    post_velo = post_ff["release_speed"].mean()

    return {
        "pre_ff_velo": pre_velo,
        "post_ff_velo": post_velo,
        "velo_change": post_velo - pre_velo,
        "pre_ff_count": len(pre_ff),
        "post_ff_count": len(post_ff)
    }

def pitch_mix_change(pre_df, post_df):
    pre_counts = pre_df["pitch_type"].value_counts(normalize=True)
    post_counts = post_df["pitch_type"].value_counts(normalize=True)

    all_pitches = set(pre_counts.index).union(set(post_counts.index))

    mix_changes = {}

    for pitch in all_pitches:
        pre_pct = pre_counts.get(pitch, 0)
        post_pct = post_counts.get(pitch, 0)
        mix_changes[f"{pitch}_pre_pct"] = pre_pct
        mix_changes[f"{pitch}_post_pct"] = post_pct
        mix_changes[f"{pitch}_delta"] = post_pct - pre_pct

    return mix_changes

cohort = pd.read_csv("../data/tj_cohort.csv")

print(cohort.head())
print(cohort.info())

cohort["mlbam_id"] = cohort["mlbam_id"].astype(int)
cohort["tj_date"] = pd.to_datetime(cohort["tj_date"])
cohort["return_date"] = pd.to_datetime(cohort["return_date"])

print(cohort.dtypes)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

os.makedirs(OUTPUT_DIR, exist_ok=True)

test_pitcher = cohort.iloc[0]
player_id = test_pitcher["mlbam_id"]
tj_date = test_pitcher["tj_date"]
return_date = test_pitcher["return_date"]

pre_data = statcast_pitcher(
    start_dt=(tj_date - pd.Timedelta(days=365)).strftime("%Y-%m-%d"),
    end_dt=tj_date.strftime("%Y-%m-%d"),
    player_id=player_id
)

print("Test pitcher:", test_pitcher["player_name"])
print("Pre-TJ pitches pulled:", len(pre_data))
print(pre_data[["pitch_type", "release_speed"]].head())
pre_data = pre_data.sort_values("game_date")
pre_300 = pre_data.tail(300).copy()

print("Pre-TJ window size:", len(pre_300))
print(pre_300[["game_date", "pitch_type", "release_speed"]].head())
print(pre_300[["game_date", "pitch_type", "release_speed"]].tail())
post_data = statcast_pitcher(
    start_dt=return_date.strftime("%Y-%m-%d"),
    end_dt=(return_date + pd.Timedelta(days=365)).strftime("%Y-%m-%d"),
    player_id=player_id
)

print("Post-return pitches pulled:", len(post_data))
post_data = post_data.sort_values("game_date")

post_300 = post_data.head(300).copy()

print("Post-return window size:", len(post_300))
print(post_300[["game_date", "pitch_type", "release_speed"]].head())
print(post_300[["game_date", "pitch_type", "release_speed"]].tail())
pre_ff = pre_300[pre_300["pitch_type"] == "FF"]
post_ff = post_300[post_300["pitch_type"] == "FF"]

print("Pre-TJ FF count:", len(pre_ff))
print("Post-return FF count:", len(post_ff))
pre_ff_velo = pre_ff["release_speed"].mean()
post_ff_velo = post_ff["release_speed"].mean()

velo_change = post_ff_velo - pre_ff_velo

print(f"Pre-TJ FF velo: {pre_ff_velo:.2f} mph")
print(f"Post-return FF velo: {post_ff_velo:.2f} mph")
print(f"Velocity change: {velo_change:.2f} mph")

results = []

for _, row in cohort.iterrows():
    player_name = row["player_name"]
    player_id = int(row["mlbam_id"])
    tj_date = row["tj_date"]
    return_date = row["return_date"]
    role_return = row["role_return"]
    role_return = row["role_return"]
    pre_win, post_win, pre_n, post_n = get_pre_post_windows(player_id, tj_date, return_date, window_pitches=300)

    if pre_win is None:
        results.append({
            "player_name": player_name,
            "mlbam_id": player_id,
            "status": "INSUFFICIENT_PITCHES",
            "pre_pitches_pulled": pre_n,
            "post_pitches_pulled": post_n,
            "role_return": role_return,
        })
        continue

    velo = fastball_velo_change(pre_win, post_win)
    mix = pitch_mix_change(pre_win, post_win)

    if velo is None:
        results.append({
            "player_name": player_name,
            "mlbam_id": player_id,
            "status": "NO_FF_DATA",
            "pre_pitches_pulled": pre_n,
            "post_pitches_pulled": post_n,
            "role_return": role_return,
        })
        continue

    results.append({
        "player_name": player_name,
        "mlbam_id": player_id,
        "status": "OK",
        "pre_pitches_pulled": pre_n,
        "post_pitches_pulled": post_n,
        "role_return": role_return,
        **velo,
        **mix
    })

results_df = pd.DataFrame(results)

for col in ["pre_ff_velo", "post_ff_velo", "velo_change"]:
    if col in results_df.columns:
        results_df[col] = results_df[col].astype(float).round(2)

mix_cols = [c for c in results_df.columns if c.endswith("_pre_pct") or c.endswith("_post_pct") or c.endswith("_delta")]
if mix_cols:
    results_df[mix_cols] = results_df[mix_cols].fillna(0)

analysis_df = results_df[results_df["status"] == "OK"].copy()
print("Number of pitchers in analysis:", len(analysis_df))

analysis_df["role_group"] = (
    analysis_df["role_return"]
    .astype(str)
    .str.strip()
    .str.upper()
)
analysis_df.loc[~analysis_df["role_group"].isin(["SP", "RP"]), "role_group"] = "SP/RP"

# save tables
analysis_df.to_csv(os.path.join(OUTPUT_DIR, "analysis_results.csv"), index=False)
results_df.to_csv(os.path.join(OUTPUT_DIR, "all_results_with_status.csv"), index=False)

# --------------------
# Pitch Mix Summary
# --------------------

KEEP_PITCHES = {"FF","SI","FT","FC","SL","CU","KC","CH","FS","ST","SV","KN"}

delta_cols = [
    c for c in analysis_df.columns
    if c.endswith("_delta") and c.split("_")[0] in KEEP_PITCHES
]

avg_mix_change = analysis_df[delta_cols].mean().sort_values()

print("\nAverage Pitch Mix Change (Post - Pre):")
print(avg_mix_change)

# Plot pitch mix change
plt.figure(figsize=(8, 5))
avg_mix_change.plot(kind="bar")
plt.axhline(0, linestyle="--")
plt.ylabel("Change in Usage %")
plt.title("Average Pitch Mix Change (First 300 Pitches Post-TJ)")
plt.tight_layout()

plt.savefig(os.path.join(OUTPUT_DIR, "pitch_mix_change.png"), dpi=300, bbox_inches="tight")
plt.show()

# --------------------
# Fastball Velocity Scatter Plot
# --------------------

plt.figure(figsize=(7, 7))

for role_label in ["SP", "RP", "SP/RP"]:
    subset = analysis_df[analysis_df["role_group"] == role_label]
    plt.scatter(
        subset["pre_ff_velo"],
        subset["post_ff_velo"],
        label=role_label
    )

min_v = min(
    analysis_df["pre_ff_velo"].min(),
    analysis_df["post_ff_velo"].min()
)
max_v = max(
    analysis_df["pre_ff_velo"].max(),
    analysis_df["post_ff_velo"].max()
)

plt.plot([min_v, max_v], [min_v, max_v], linestyle="--")

plt.xlabel("Pre-TJ Fastball Velocity (mph)")
plt.ylabel("Post-Return Fastball Velocity (mph)")
plt.title("Fastball Velocity: Pre-TJ vs Post-Return (First 300 Pitches)")
plt.legend()
plt.tight_layout()

plt.savefig(os.path.join(OUTPUT_DIR, "ff_velo_pre_vs_post_by_role.png"), dpi=300, bbox_inches="tight")
plt.show()

avg_velo_change = analysis_df["velo_change"].mean()
std_velo_change = analysis_df["velo_change"].std()

print(f"\nAverage FF velocity change: {avg_velo_change:.2f} mph")
print(f"Standard deviation: {std_velo_change:.2f} mph")

sl_change = analysis_df["SL_delta"].mean() * 100
cu_change = analysis_df["CU_delta"].mean() * 100

print(f"Average slider usage change: {sl_change:.1f} percentage points")
print(f"Average curveball usage change: {cu_change:.1f} percentage points")






