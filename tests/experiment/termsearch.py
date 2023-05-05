from argparse import ArgumentParser
from pprint import pprint
from nidm.experiment import Utils


def main():
    parser = ArgumentParser(
        description="This program will query SciCrunch term labels for query_string using key and print out the return JSON packet."
    )
    parser.add_argument(
        "-query_string", dest="query_string", required=True, help="Query String"
    )
    parser.add_argument(
        "-key", dest="key", required=True, help="SciCrunch API key to use for query"
    )
    args = parser.parse_args()

    # Test exact match search returning JSON package
    print("Testing term label search...")
    json_data = Utils.QuerySciCrunchTermLabel(args.key, args.query_string)
    print("Term label search returns:")
    print("-------------------------------------------")
    pprint(json_data)
    print("\n\n")

    # Test elastic search using CDEs and Terms + ancestors (simulates tagging sets of terms for NIDM use) returning JSON package
    print("Testing elastic search...")
    json_data = Utils.QuerySciCrunchElasticSearch(args.key, args.query_string)
    print("Elastic search returns:")
    print("-------------------------------------------")
    pprint(json_data)
    #  print("\n\n-------------------------------------------")
    #  print("Example terms listing from elastic search:")

    # example printing term label, definition, and preferred URL
    #  for term in json_data['hits']['hits']:
    #      #find preferred URL
    #      for items in term['_source']['existing_ids']:
    #          if items['preferred']=='1':
    #              preferred_url=items['iri']
    #      print(f"Label = {term['_source']['label']} \t Definition = {term['_source']['definition']} \t Preferred URL = {preferred_url} ")

    # example of uber elastic search query returns dictionary of label, definition, and preferred_url
    print("\n\n-------------------------------------------")
    print("Example uber elastic search:")
    results = Utils.GetNIDMTermsFromSciCrunch(args.key, args.query_string)
    for value in results.values():
        print(
            "Label: {label} \t Definition: {definition} \t Preferred URL: {preferred_url} ".format_map(
                value
            )
        )


if __name__ == "__main__":
    main()


# very simple test, just checking if main does not give any error
def test_main():
    main()
