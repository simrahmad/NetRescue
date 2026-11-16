"""Charts for the report.  OWNER: M5"""


def load_results(csv_path):
    """Return a pandas DataFrame from a results CSV.  TODO."""
    raise NotImplementedError


def plot_comparison(df, metric, out_path):
    """Bar chart of mean `metric` per scenario for baseline vs adaptive,
    with error bars (standard deviation).  Save to out_path (PNG).

    TODO: explain in the report any scenario where adaptive is worse.
    """
    raise NotImplementedError