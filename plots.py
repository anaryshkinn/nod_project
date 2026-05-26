import matplotlib.pyplot as plt


def make_plots(df):
    countries = (
        df["country"]
        .dropna()
        .str.split(", ")
        .explode()
        .value_counts()
        .head(10)
    )

    countries.plot(kind="bar", figsize=(10, 5), title="Top countries in current dataset")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.show()

    genres = (
        df["genre"]
        .dropna()
        .str.split(", ")
        .explode()
        .value_counts()
        .head(10)
    )

    genres.plot(kind="bar", figsize=(10, 5), title="Top genres in current dataset")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.show()

    df["rating_tmdb"].dropna().plot(
        kind="hist",
        bins=15,
        figsize=(8, 5),
        title="TMDb rating distribution"
    )
    plt.tight_layout()
    plt.show()

    df["source_parsing"].value_counts().plot(
        kind="bar",
        figsize=(6, 5),
        title="Moskino vs Pioner"
    )
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.show()


def make_candidate_plots(df):
    if "festival" in df.columns:
        df["festival"].value_counts().plot(
            kind="bar",
            figsize=(8, 5),
            title="Candidate films by festival"
        )
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.show()

    year_col = "year_festival" if "year_festival" in df.columns else "year"
    if year_col in df.columns:
        df[year_col].value_counts().sort_index().plot(
            kind="bar",
            figsize=(8, 5),
            title="Candidate films by year"
        )
        plt.xticks(rotation=0)
        plt.tight_layout()
        plt.show()

    if "award" in df.columns:
        df["award"].value_counts().head(10).plot(
            kind="bar",
            figsize=(10, 5),
            title="Top awards among candidate films"
        )
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        plt.show()
