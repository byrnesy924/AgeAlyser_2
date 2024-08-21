class ProductionBuilding():
    """TODO This class models the function of a production building, including creating units, storing upgrades, measuring idle time"""
    def __init__(self,
                 building_type: str,
                 building_units: list,
                 civilisation: str,
                 unit_queue_times: pd.DataFrame,
                 relevant_technologytimes: pd.DataFrame,
                 building_id: int = None  # Data may limit this being able to be used
                 ) -> None:
        # Parse information

        # TODO add error handling that all civilisations are valid, all units passed are valid, the type of building is valid

        pass

    def produce_units(self) -> pd.DataFrame:
        """Take the time stamps of units, as well as the upgrades, and work out when they wouldve been produced,
        taking into account 1 at a time creation (i.e., queuing)

        :return pd.DataFrame: a dataframe of units and when they were created

        """
        pass